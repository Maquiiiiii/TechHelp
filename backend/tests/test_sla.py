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
    
    # Completa previamente 3 organizaciones de prueba con diferentes niveles de SLA
    org_oro = await OrganizationDAO.create(
        name="Org Oro",
        rut="11111111-1",
        email="client@oro.cl",
        nivel_soporte="Oro"
    )
    org_plata = await OrganizationDAO.create(
        name="Org Plata",
        rut="22222222-2",
        email="client@plata.cl",
        nivel_soporte="Plata"
    )
    org_bronce = await OrganizationDAO.create(
        name="Org Bronce",
        rut="33333333-3",
        email="client@bronce.cl",
        nivel_soporte="Bronce"
    )
    
    yield {"Oro": org_oro, "Plata": org_plata, "Bronce": org_bronce}
    await db[OrganizationDAO.collection_name].delete_many({})
    await db[TicketDAO.collection_name].delete_many({})
    Database.close_db()

@pytest.mark.anyio
async def test_dynamic_sla_on_ticket_creation(setup_db):
    """Test that ticket creation calculates dynamic SLA windows based on contract support tiers (RF-024)."""
    orgs = setup_db

    # 1. Nivel Oro + prioridad Alta: la ventana de resolución debe ser de 30 minutos
    ticket1 = await TicketDAO.create(
        title="Error Critico",
        description="Fallo de sistema centralizado de transacciones financieras corporativas.",
        customer_id=orgs["Oro"]["rut"],
        categoria="Software",
        prioridad="Alta"
    )
    assert ticket1["tiempo_maximo_resolucion"] == 30
    assert ticket1["nivel_soporte_org"] == "Oro"

    # 2. Nivel Plata + prioridad Alta: la ventana de resolución debe ser de 60 minutos
    ticket2 = await TicketDAO.create(
        title="Error Redes",
        description="Fallo de switches core de oficina de operaciones y sucursales.",
        customer_id=orgs["Plata"]["rut"],
        categoria="Redes",
        prioridad="Alta"
    )
    assert ticket2["tiempo_maximo_resolucion"] == 60
    assert ticket2["nivel_soporte_org"] == "Plata"

    # 3. Nivel Bronce + prioridad Alta: la ventana de resolución debe ser de 120 minutos
    ticket3 = await TicketDAO.create(
        title="Fallo Impresion",
        description="Impresoras general bloqueadas en la oficina central de retail.",
        customer_id=orgs["Bronce"]["rut"],
        categoria="Hardware",
        prioridad="Alta"
    )
    assert ticket3["tiempo_maximo_resolucion"] == 120
    assert ticket3["nivel_soporte_org"] == "Bronce"

@pytest.mark.anyio
async def test_reclassify_priority_recalculation(setup_db):
    """Test reclassifying ticket priority and recalculating SLA deadline from now (RF-016)."""
    orgs = setup_db
    # Crear un boleto Oro en prioridad Baja (ventana: 120 minutos)
    ticket = await TicketDAO.create(
        title="Duda General",
        description="Pregunta general de facturacion y cobros del mes calendario anterior.",
        customer_id=orgs["Oro"]["rut"],
        categoria="Software",
        prioridad="Baja"
    )
    assert ticket["tiempo_maximo_resolucion"] == 120

    admin_token = create_access_token({"sub": "admin@techhelp.cl", "role": "Administrador"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    payload = {
        "prioridad": "Alta",
        "justificacion": "Se escaló debido a impacto crítico en producción reportado posteriormente.",
        "version": ticket["__v"]
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.put(f"/api/v1/tickets/{ticket['_id']}/priority", json=payload, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["prioridad"] == "Alta"
        # Ventana actualizada a 30 minutos.
        assert data["tiempo_maximo_resolucion"] == 30
        
        # Verifique que la fecha límite esté establecida a partir de ahora (ahora + 30 minutos), no creada_en + 30 minutos
        expiration = datetime.fromisoformat(data["fecha_expiracion_sla"].replace("Z", "+00:00")).replace(tzinfo=None)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        diff_minutes = (expiration - now).total_seconds() / 60
        # Debería estar muy cerca de los 30 minutos.
        assert 28.0 < diff_minutes < 32.0


@pytest.mark.anyio
async def test_priority_reclassification_validation_failures(setup_db):
    """Test validation errors for short justifications and role restriction blocks (RF-016)."""
    orgs = setup_db
    ticket = await TicketDAO.create(
        title="Duda VPN",
        description="Pregunta de configuracion inicial de perfiles vpn forticlient.",
        customer_id=orgs["Oro"]["rut"],
        categoria="Software",
        prioridad="Baja"
    )

    # 1. Justificación breve (error de validación: min_length=10)
    admin_token = create_access_token({"sub": "admin@techhelp.cl", "role": "Administrador"})
    headers_admin = {"Authorization": f"Bearer {admin_token}"}
    payload_short = {"prioridad": "Alta", "justificacion": "Corta", "version": ticket["__v"]}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.put(f"/api/v1/tickets/{ticket['_id']}/priority", json=payload_short, headers=headers_admin)
        assert response.status_code == 422

        # 2. Bloque de solicitud de rol de técnico (prohibido: 403)
        tech_token = create_access_token({"sub": "tecnico@techhelp.cl", "role": "Tecnico"})
        headers_tech = {"Authorization": f"Bearer {tech_token}"}
        payload_valid = {"prioridad": "Alta", "justificacion": "Justificación suficientemente larga para pasar.", "version": ticket["__v"]}
        response = await ac.put(f"/api/v1/tickets/{ticket['_id']}/priority", json=payload_valid, headers=headers_tech)
        assert response.status_code == 403