import os
import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone, timedelta
from bson import ObjectId

# Forzar la prueba del URI de la base de datos antes de las importaciones
os.environ["MONGO_URI"] = "mongodb://localhost:27017/techhelp_test_db"

from backend.main import app
from backend.config.database import Database
from backend.dao.organization_dao import OrganizationDAO
from backend.dao.ticket_dao import TicketDAO
from backend.security.auth import create_access_token
from backend.tasks.sla_monitor import auto_close_resolved_tickets

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.fixture
async def setup_db(anyio_backend):
    """Initializes connection to test database, registers indexing, and cleans up before and after the test."""
    db = Database.get_db()
    await OrganizationDAO.create_indexes()
    await TicketDAO.create_indexes()
    await db[OrganizationDAO.collection_name].delete_many({})
    await db[TicketDAO.collection_name].delete_many({})
    
    # Completar previamente una organización de prueba
    org = await OrganizationDAO.create(
        name="Routing Client Org",
        rut="12345678-5",
        email="client@routing.cl"
    )
    
    yield org
    await db[OrganizationDAO.collection_name].delete_many({})
    await db[TicketDAO.collection_name].delete_many({})
    Database.close_db()

@pytest.mark.anyio
async def test_resolved_auto_closer_sweep(setup_db):
    """Test background loop sweep auto-closing resolved tickets older than 5 working days."""
    org = setup_db
    # Crear ticket en estado Resuelto con resuelto_at hace 7 días naturales (5 días hábiles)
    db = Database.get_db()
    ticket_doc = {
        "code": "TK-88888",
        "title": "Incidente Viejo",
        "description": "Fallo persistente de hardware en servidores centrales de respaldo.",
        "status": "Resuelto",
        "customer_id": org["rut"],
        "categoria": "Hardware",
        "prioridad": "Alta",
        "comentario_solucion": "Solucionado reiniciando el rack central.",
        "resuelto_at": datetime.now(timezone.utc) - timedelta(days=7),
        "__v": 0,
        "created_at": datetime.now(timezone.utc) - timedelta(days=10)
    }
    result = await db["tickets"].insert_one(ticket_doc)
    ticket_id = str(result.inserted_id)

    # Ejecutar barrido de cierre automático
    await auto_close_resolved_tickets()

    # Verificar que el estado haya cambiado a Cerrado
    updated = await TicketDAO.get_by_id(ticket_id)
    assert updated["status"] == "Cerrado"

    # Verificar que el comentario sobre el ticket de Cerrado falle
    with pytest.raises(Exception) as exc:
        await TicketDAO.add_comment(
            ticket_id=ticket_id,
            comment_text="Intento de nota en ticket cerrado",
            es_interno=False,
            author_email="tecnico@techhelp.cl",
            author_role="Tecnico"
        )
    assert "No se pueden añadir comentarios" in str(exc.value)

@pytest.mark.anyio
async def test_re_route_rejection_success(setup_db):
    """Test putting a ticket to 'Rechazado' state when no new category is provided."""
    org = setup_db
    ticket = await TicketDAO.create(
        title="Error de Redes",
        description="Fallo de switches cisco en la oficina de contabilidad general.",
        customer_id=org["rut"],
        categoria="Redes",
        prioridad="Media"
    )
    ticket_id = ticket["_id"]

    tech_token = create_access_token({"sub": "tecnico@techhelp.cl", "role": "Tecnico"})
    headers = {"Authorization": f"Bearer {tech_token}"}

    payload = {
        "motivo": "Rechazado porque no corresponde a soporte de red local, excede límites contractuales.",
        "version": ticket["__v"]
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(f"/api/v1/tickets/{ticket_id}/re-route", json=payload, headers=headers)
        # Espera, el punto final es PUT /tickets/{id}/re-route
        response = await ac.put(f"/api/v1/tickets/{ticket_id}/re-route", json=payload, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "Rechazado"
        # Verifique que se haya agregado el comentario interno del sistema
        assert len(data["comentarios"]) == 1
        assert "Re-enrutamiento/Rechazo" in data["comentarios"][0]["texto"]

@pytest.mark.anyio
async def test_re_route_recategorization_success(setup_db):
    """Test recategorizing a ticket, resetting SLA counters and setting status back to Abierto."""
    org = setup_db
    # Crear ticket en estado En Espera para tener minutos de espera acumulados
    db = Database.get_db()
    ticket_doc = {
        "code": "TK-99999",
        "title": "Error de Impresora",
        "description": "Fallo de drivers en la impresora laser de recepcion general.",
        "status": "En Espera",
        "customer_id": org["rut"],
        "categoria": "Hardware",
        "prioridad": "Media",
        "minutos_en_espera_acumulados": 45.5,
        "assigned_tech_id": "some-tech-id",
        "assigned_tech_name": "Juan Perez",
        "__v": 2,
        "created_at": datetime.now(timezone.utc) - timedelta(hours=2)
    }
    result = await db["tickets"].insert_one(ticket_doc)
    ticket_id = str(result.inserted_id)

    tech_token = create_access_token({"sub": "tecnico@techhelp.cl", "role": "Tecnico"})
    headers = {"Authorization": f"Bearer {tech_token}"}

    payload = {
        "motivo": "El problema es de software (drivers), no de hardware físico. Recategorizando.",
        "nueva_categoria": "Software",
        "version": 2
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.put(f"/api/v1/tickets/{ticket_id}/re-route", json=payload, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "Abierto"
        assert data["categoria"] == "Software"
        assert data["assigned_tech_id"] is None
        assert data["assigned_tech_name"] is None

        # Consultar la base de datos directamente para verificar el restablecimiento del SLA interno
        db_doc = await db["tickets"].find_one({"_id": ObjectId(ticket_id)})
        assert db_doc["minutos_en_espera_acumulados"] == 0.0


@pytest.mark.anyio
async def test_re_route_validation_failures(setup_db):
    """Test validation errors for short motifs and role restriction blocks."""
    org = setup_db
    ticket = await TicketDAO.create(
        title="Error de VPN",
        description="Fallo de inicio de sesion VPN forticlient desde sucursales.",
        customer_id=org["rut"],
        categoria="Software",
        prioridad="Alta"
    )
    ticket_id = ticket["_id"]

    # 1. Motivo breve (error de validación: min_length=15)
    tech_token = create_access_token({"sub": "tecnico@techhelp.cl", "role": "Tecnico"})
    headers_tech = {"Authorization": f"Bearer {tech_token}"}
    payload_short = {"motivo": "Corto", "version": ticket["__v"]}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.put(f"/api/v1/tickets/{ticket_id}/re-route", json=payload_short, headers=headers_tech)
        assert response.status_code == 422

        # 2. Bloqueo de solicitud de rol de cliente (prohibido: 403)
        client_token = create_access_token({"sub": "client@routing.cl", "role": "Cliente"})
        headers_client = {"Authorization": f"Bearer {client_token}"}
        payload_valid = {"motivo": "Motivo suficientemente largo para superar validación.", "version": ticket["__v"]}
        response = await ac.put(f"/api/v1/tickets/{ticket_id}/re-route", json=payload_valid, headers=headers_client)
        assert response.status_code == 403