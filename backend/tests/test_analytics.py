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
    await db["survey_tokens"].delete_many({})
    await db["satisfaccion_cliente"].delete_many({})
    
    # Completar previamente una organización de prueba
    org = await OrganizationDAO.create(
        name="Analytics Client Org",
        rut="12345678-5",
        email="client@analytics.cl"
    )
    
    yield org
    await db[OrganizationDAO.collection_name].delete_many({})
    await db[TicketDAO.collection_name].delete_many({})
    await db["survey_tokens"].delete_many({})
    await db["satisfaccion_cliente"].delete_many({})
    Database.close_db()

@pytest.mark.anyio
async def test_mttr_report_generation(setup_db):
    """Test generating MTTR report and downloading as CSV with valid dates."""
    org = setup_db
    db = Database.get_db()

    # Rellenar previamente tickets cerrados resueltos por un técnico
    ticket1_doc = {
        "code": "TK-11111",
        "title": "Fallo Base de Datos",
        "description": "Timeout general en el motor de base de datos relacional primario.",
        "status": "Cerrado",
        "customer_id": org["rut"],
        "categoria": "Bases de Datos",
        "prioridad": "Alta",
        "assigned_tech_id": "tech_juan",
        "assigned_tech_name": "Juan Perez",
        "created_at": datetime.now(timezone.utc) - timedelta(hours=3),
        "resuelto_at": datetime.now(timezone.utc) - timedelta(hours=1), # Tiempo de resolución de 2 horas = 120 minutos
        "__v": 1
    }
    
    await db["tickets"].insert_one(ticket1_doc)

    admin_token = create_access_token({"sub": "admin@techhelp.cl", "role": "Administrador"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    # rango de consulta
    start_str = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    end_str = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Descarga exitosa
        response = await ac.get(f"/api/v1/reports/mttr?fecha_inicio={start_str}&fecha_fin={end_str}", headers=headers)
        print("STATUS:", response.status_code)
        print("BODY:", response.text)
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        content = response.text
        assert "ID Tecnico,Nombre Tecnico,Volumen Resuelto,MTTR (Minutos)" in content
        assert "tech_juan,Juan Perez,1,120" in content

        # 2. Error de validación del rango de fechas (inicio > fin)
        bad_start = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        response_bad = await ac.get(f"/api/v1/reports/mttr?fecha_inicio={bad_start}&fecha_fin={end_str}", headers=headers)
        assert response_bad.status_code == 400
        assert "Rango de fechas inválido" in response_bad.json()["detail"]

@pytest.mark.anyio
async def test_survey_token_generation_on_closing(setup_db):
    """Test that closing a ticket automatically generates a survey token and dispatches simulated email."""
    org = setup_db
    
    # Crear ticket resuelto
    db = Database.get_db()
    ticket_doc = {
        "code": "TK-22222",
        "title": "Fallo Conectividad",
        "description": "El balanceador central no responde peticiones entrantes de clientes.",
        "status": "Resuelto",
        "customer_id": org["rut"],
        "categoria": "Redes",
        "prioridad": "Alta",
        "assigned_tech_id": "tech_marcos",
        "assigned_tech_name": "Marcos Diaz",
        "created_at": datetime.now(timezone.utc) - timedelta(hours=5),
        "resuelto_at": datetime.now(timezone.utc) - timedelta(hours=4),
        "__v": 1
    }
    result = await db["tickets"].insert_one(ticket_doc)
    ticket_id = str(result.inserted_id)

    # Realizar cambio de estado a cerrado
    await TicketDAO.update_status(
        ticket_id=ticket_id,
        current_version=1,
        new_status="Cerrado"
    )

    # Verificar que existe un token en Survey_tokens
    token_doc = await db["survey_tokens"].find_one({"ticket_id": ticket_id})
    assert token_doc is not None
    assert token_doc["customer_email"] == org["email"]
    assert token_doc["tech_id"] == "tech_marcos"
    assert token_doc["tech_name"] == "Marcos Diaz"
    assert token_doc["used"] is False
    expires_at = token_doc["expires_at"].replace(tzinfo=timezone.utc) if token_doc["expires_at"].tzinfo is None else token_doc["expires_at"]
    assert (expires_at - datetime.now(timezone.utc)).total_seconds() > 47 * 3600 # Válido por 48 horas


@pytest.mark.anyio
async def test_feedback_submission_rules(setup_db):
    """Test feedback submission token checks, value thresholds, and non-mutation strict rules."""
    org = setup_db
    db = Database.get_db()

    # Complete previamente un token de encuesta
    token = "crypto_secure_token_123"
    expires_at = datetime.now(timezone.utc) + timedelta(hours=48)
    token_doc = {
        "token": token,
        "ticket_id": "some_ticket_id",
        "customer_email": org["email"],
        "tech_id": "tech_juan",
        "tech_name": "Juan Perez",
        "expires_at": expires_at,
        "used": False
    }
    await db["survey_tokens"].insert_one(token_doc)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Fallo de validación: calificación fuera de límites (> 5)
        payload_bad_rating = {"token": token, "valoracion": 6, "comentarios": "Excelente"}
        response = await ac.post("/api/v1/feedback", json=payload_bad_rating)
        assert response.status_code == 422

        # 2. Envío exitoso (calificación 5)
        payload_ok = {"token": token, "valoracion": 5, "comentarios": "Excelente soporte!"}
        response = await ac.post("/api/v1/feedback", json=payload_ok)
        assert response.status_code == 201
        data = response.json()
        assert data["valoracion"] == 5
        assert data["tech_id"] == "tech_juan"
        assert data["tech_name"] == "Juan Perez"

        # Consultar entrada de base de datos en satisfaccion_cliente
        feedback_entry = await db["satisfaccion_cliente"].find_one({"token": token})
        # Espera, la entrada de comentarios tiene ticket_id, sin token. Busquémoslo por ticket_id:
        feedback_entry = await db["satisfaccion_cliente"].find_one({"ticket_id": "some_ticket_id"})
        assert feedback_entry is not None
        assert feedback_entry["valoracion"] == 5

        # 3. Bloqueo de reutilización de token: el envío nuevamente con el mismo token debería fallar
        response_reuse = await ac.post("/api/v1/feedback", json=payload_ok)
        assert response_reuse.status_code == 400
        assert "ya ha sido utilizado" in response_reuse.json()["error"]

        # 4. Verificación de vencimiento: inserte el token vencido
        expired_token = "expired_token_abc"
        expired_token_doc = {
            "token": expired_token,
            "ticket_id": "some_ticket_id_2",
            "customer_email": org["email"],
            "tech_id": "tech_juan",
            "tech_name": "Juan Perez",
            "expires_at": datetime.now(timezone.utc) - timedelta(hours=1), # Caducó hace 1 hora
            "used": False
        }
        await db["survey_tokens"].insert_one(expired_token_doc)
        payload_expired = {"token": expired_token, "valoracion": 4}
        response_exp = await ac.post("/api/v1/feedback", json=payload_expired)
        assert response_exp.status_code == 400
        assert "ha expirado" in response_exp.json()["error"]


@pytest.mark.anyio
async def test_organizations_by_ticket_count_filter(setup_db):
    """Test filtering organizations by range of tickets count and RBAC checks."""
    org_with_tickets = setup_db
    db = Database.get_db()

    # 1. Crea una segunda organización que tendrá 0 entradas.
    org_no_tickets = await OrganizationDAO.create(
        name="Zero Tickets Org",
        rut="98765432-1",
        email="zero@analytics.cl"
    )

    # 2. Inserta 2 entradas para la primera organización.
    tickets = [
        {
            "code": "TK-80001",
            "title": "Problem 1",
            "description": "Short description long enough to satisfy.",
            "status": "Abierto",
            "customer_id": org_with_tickets["rut"],
            "categoria": "Hardware",
            "prioridad": "Baja",
            "created_at": datetime.now(timezone.utc),
            "__v": 0
        },
        {
            "code": "TK-80002",
            "title": "Problem 2",
            "description": "Short description long enough to satisfy.",
            "status": "Asignado",
            "customer_id": org_with_tickets["rut"],
            "categoria": "Software",
            "prioridad": "Media",
            "created_at": datetime.now(timezone.utc),
            "__v": 0
        }
    ]
    await db["tickets"].insert_many(tickets)

    admin_token = create_access_token({"sub": "admin@techhelp.cl", "role": "Administrador"})
    client_token = create_access_token({"sub": "client@analytics.cl", "role": "Cliente"})
    
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    client_headers = {"Authorization": f"Bearer {client_token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # A. Consulta sin parámetros (rol de administrador) -> Devuelve ambos
        res = await ac.get("/api/v1/dashboard/organizations-by-ticket-count", headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 2
        
        # Verificar el recuento de entradas
        org_1 = next(item for item in data if item["rut"] == org_with_tickets["rut"])
        org_2 = next(item for item in data if item["rut"] == org_no_tickets["rut"])
        assert org_1["tickets_count"] == 2
        assert org_2["tickets_count"] == 0

        # B. Consulta con tickets_min = 1 -> Devuelve solo el que tiene 2 tickets
        res_min = await ac.get("/api/v1/dashboard/organizations-by-ticket-count?tickets_min=1", headers=admin_headers)
        assert res_min.status_code == 200
        data_min = res_min.json()
        assert len(data_min) == 1
        assert data_min[0]["rut"] == org_with_tickets["rut"]

        # C. Consulta con tickets_max = 1 -> Devuelve solo el que tiene 0 tickets
        res_max = await ac.get("/api/v1/dashboard/organizations-by-ticket-count?tickets_max=1", headers=admin_headers)
        assert res_max.status_code == 200
        data_max = res_max.json()
        assert len(data_max) == 1
        assert data_max[0]["rut"] == org_no_tickets["rut"]

        # D. Consulta con tickets_min = 1 y tickets_max = 3 -> Devuelve el que tiene 2 tickets
        res_range = await ac.get("/api/v1/dashboard/organizations-by-ticket-count?tickets_min=1&tickets_max=3", headers=admin_headers)
        assert res_range.status_code == 200
        data_range = res_range.json()
        assert len(data_range) == 1
        assert data_range[0]["rut"] == org_with_tickets["rut"]

        # E. Consulta como Cliente -> Prohibido 403
        res_client = await ac.get("/api/v1/dashboard/organizations-by-ticket-count", headers=client_headers)
        assert res_client.status_code == 403
        assert "privilegios" in res_client.json()["detail"].lower()