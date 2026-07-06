import os
import pytest
from httpx import AsyncClient, ASGITransport
from bson import ObjectId
from datetime import datetime, timezone, timedelta

# Forzar la prueba del URI de la base de datos antes de las importaciones
os.environ["MONGO_URI"] = "mongodb://localhost:27017/techhelp_test_db"

from backend.main import app
from backend.config.database import Database
from backend.dao.organization_dao import OrganizationDAO
from backend.dao.ticket_dao import TicketDAO
from backend.dao.dashboard_dao import DashboardDAO
from backend.security.auth import create_access_token

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.fixture
async def setup_db(anyio_backend):
    """Initializes connection to test database and pre-populates test data."""
    db = Database.get_db()
    await OrganizationDAO.create_indexes()
    await TicketDAO.create_indexes()
    await db[OrganizationDAO.collection_name].delete_many({})
    await db[TicketDAO.collection_name].delete_many({})
    await db["satisfaccion_cliente"].delete_many({})
    
    # 1. Crear una organización de clientes
    org = await OrganizationDAO.create(
        name="TechHelp Client Org",
        rut="12345678-5",
        email="client@techhelp.cl"
    )
    
    # 2. Crear ticket bajo organización
    ticket = await TicketDAO.create(
        title="VPN Setup Issue",
        description="Unable to connect to the corporate VPN.",
        customer_id="12345678-5",
        categoria="Redes",
        prioridad="Media"
    )
    
    yield {"org": org, "ticket": ticket}
    
    await db[OrganizationDAO.collection_name].delete_many({})
    await db[TicketDAO.collection_name].delete_many({})
    await db["satisfaccion_cliente"].delete_many({})
    Database.close_db()

@pytest.mark.anyio
async def test_submit_direct_feedback_unauthorized(setup_db):
    """Verify that only Client roles can submit feedback."""
    ticket_id = setup_db["ticket"]["_id"]
    tech_token = create_access_token({"sub": "tech@techhelp.cl", "role": "Tecnico"})
    headers = {"Authorization": f"Bearer {tech_token}"}
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            f"/api/v1/tickets/{ticket_id}/feedback",
            json={"valoracion": 4, "comentarios": "Buen servicio"},
            headers=headers
        )
        assert response.status_code == 403
        assert "Acceso denegado" in response.json()["detail"]

@pytest.mark.anyio
async def test_submit_direct_feedback_wrong_status(setup_db):
    """Verify feedback fails if ticket is not Cerrado."""
    ticket_id = setup_db["ticket"]["_id"]
    client_token = create_access_token({"sub": "client@techhelp.cl", "role": "Cliente"})
    headers = {"Authorization": f"Bearer {client_token}"}
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            f"/api/v1/tickets/{ticket_id}/feedback",
            json={"valoracion": 5, "comentarios": "Excelente"},
            headers=headers
        )
        assert response.status_code == 400
        assert "estado Cerrado" in response.json()["error"]

@pytest.mark.anyio
async def test_submit_direct_feedback_happy_path(setup_db):
    """Verify successful feedback submission for a Cerrado ticket."""
    db = Database.get_db()
    ticket_id = setup_db["ticket"]["_id"]
    
    # Cierre previamente el ticket en la base de datos directamente para evitar las reglas de la máquina de estado
    await db[TicketDAO.collection_name].update_one(
        {"_id": ObjectId(ticket_id)},
        {"$set": {"status": "Cerrado"}}
    )
    
    client_token = create_access_token({"sub": "client@techhelp.cl", "role": "Cliente"})
    headers = {"Authorization": f"Bearer {client_token}"}
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            f"/api/v1/tickets/{ticket_id}/feedback",
            json={"valoracion": 5, "comentarios": "Servicio de alta calidad"},
            headers=headers
        )
        assert response.status_code == 201
        assert "Reseña registrada con éxito" in response.json()["message"]
        
        # Verificar que se recace el envío duplicado
        res2 = await ac.post(
            f"/api/v1/tickets/{ticket_id}/feedback",
            json={"valoracion": 5, "comentarios": "Segundo intento"},
            headers=headers
        )
        assert res2.status_code == 400
        assert "ya fue respondida" in res2.json()["error"]

@pytest.mark.anyio
async def test_churn_risk_alerts_calculation(setup_db):
    """Verify get_churn_risk_alerts pipeline aggregates correctly."""
    db = Database.get_db()
    ticket_id = setup_db["ticket"]["_id"]
    
    # 1. Actualizar el ticket para que se cierre y caduque (violación del SLA)
    now = datetime.now(timezone.utc)
    expired_sla = now - timedelta(hours=2)
    
    await db[TicketDAO.collection_name].update_one(
        {"_id": ObjectId(ticket_id)},
        {"$set": {
            "status": "Cerrado",
            "resuelto_at": now,
            "fecha_expiracion_sla": expired_sla,
            "created_at": now - timedelta(days=1)
        }}
    )
    
    # 2. Añade malos comentarios (2 estrellas)
    await db["satisfaccion_cliente"].insert_one({
        "ticket_id": ticket_id,
        "customer_email": "client@techhelp.cl",
        "valoracion": 2,
        "created_at": now
    })
    
    # 3. Activar alertas de riesgo
    alerts = await DashboardDAO.get_churn_risk_alerts()
    
    assert len(alerts) == 1
    org_alert = alerts[0]
    assert org_alert["organization_name"] == "TechHelp Client Org"
    assert org_alert["sla_violation_percentage"] == 100.0
    assert org_alert["average_survey_rating"] == 2.0
    assert org_alert["riesgo_inminente"] is True