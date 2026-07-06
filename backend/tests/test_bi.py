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
    await db["survey_tokens"].delete_many({})
    await db["satisfaccion_cliente"].delete_many({})
    
    # Complete previamente dos organizaciones de prueba
    org_risk = await OrganizationDAO.create(
        name="Risk Customer Org",
        rut="12345678-5",
        email="client@risk.cl",
        nivel_soporte="Oro"
    )
    
    org_safe = await OrganizationDAO.create(
        name="Safe Customer Org",
        rut="87654321-2",
        email="client@safe.cl",
        nivel_soporte="Oro"
    )
    
    yield {"risk": org_risk, "safe": org_safe}
    await db[OrganizationDAO.collection_name].delete_many({})
    await db[TicketDAO.collection_name].delete_many({})
    await db["survey_tokens"].delete_many({})
    await db["satisfaccion_cliente"].delete_many({})
    Database.close_db()

@pytest.mark.anyio
async def test_churn_risk_early_warning_alert(setup_db):
    """Test that customer churn risks are correctly computed based on SLA and satisfaction criteria (RF-025)."""
    orgs = setup_db
    db = Database.get_db()
    
    # --- 1. CONFIGURAR LA ORGANIZACIÓN DE RIESGO (tasa de incumplimiento del SLA 100 % (>15 %), promedio de satisfacción 1,5 (<2,5)) ---
    # Crear un ticket para la organización de riesgo
    t_risk_doc = {
        "code": "TK-11111",
        "title": "Fallo Critico Servidor",
        "description": "Fallo completo de hardware de rack primario en data center corporativo.",
        "status": "Cerrado",
        "customer_id": orgs["risk"]["rut"],
        "categoria": "Hardware",
        "prioridad": "Alta",
        "sla_vencido": True,  # SLA violado
        "created_at": datetime.now(timezone.utc) - timedelta(days=5),
        "resuelto_at": datetime.now(timezone.utc) - timedelta(days=4),
        "__v": 1
    }
    result_risk = await db["tickets"].insert_one(t_risk_doc)
    ticket_risk_id = str(result_risk.inserted_id)

    # Enviar comentarios con calificación baja (1 estrella) vinculados a este ticket
    feedback_risk = {
        "ticket_id": ticket_risk_id,
        "customer_email": orgs["risk"]["email"],
        "valoracion": 1,
        "comentarios": "Mala atención y retrasos.",
        "created_at": datetime.now(timezone.utc) - timedelta(days=4)
    }
    await db["satisfaccion_cliente"].insert_one(feedback_risk)

    # --- 2. CONFIGURAR UNA ORGANIZACIÓN SEGURA (tasa de compensación de SLA 0 %, promedio de satisfacción 5,0) ---
    t_safe_doc = {
        "code": "TK-22222",
        "title": "Duda Software",
        "description": "Problemas menores de configuración de accesos a perfiles VPN corporativos.",
        "status": "Cerrado",
        "customer_id": orgs["safe"]["rut"],
        "categoria": "Software",
        "prioridad": "Baja",
        "sla_vencido": False, # SLA cumplido
        "created_at": datetime.now(timezone.utc) - timedelta(days=5),
        "resuelto_at": datetime.now(timezone.utc) - timedelta(days=4),
        "__v": 1
    }
    result_safe = await db["tickets"].insert_one(t_safe_doc)
    ticket_safe_id = str(result_safe.inserted_id)

    feedback_safe = {
        "ticket_id": ticket_safe_id,
        "customer_email": orgs["safe"]["email"],
        "valoracion": 5,
        "comentarios": "Soporte excelente!",
        "created_at": datetime.now(timezone.utc) - timedelta(days=4)
    }
    await db["satisfaccion_cliente"].insert_one(feedback_safe)

    # --- 3. PUNTO FINAL DE EVALUACIÓN DEL ACTIVADOR ---
    admin_token = create_access_token({"sub": "admin@techhelp.cl", "role": "Administrador"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/analytics/churn-risk", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verificar predicciones
        risk_org_res = next(x for x in data if x["customer_id"] == orgs["risk"]["rut"])
        assert risk_org_res["riesgo_inminente_cancelacion"] is True
        assert risk_org_res["tasa_violacion_sla"] == 1.0
        assert risk_org_res["satisfaccion_promedio"] == 1.0

        safe_org_res = next(x for x in data if x["customer_id"] == orgs["safe"]["rut"])
        assert safe_org_res["riesgo_inminente_cancelacion"] is False
        assert safe_org_res["tasa_violacion_sla"] == 0.0
        assert safe_org_res["satisfaccion_promedio"] == 5.0

@pytest.mark.anyio
async def test_capacity_projection_trends(setup_db):
    """Test monthly technical capacity projections and hiring alert triggers (RF-026)."""
    orgs = setup_db
    db = Database.get_db()

    # Calcular año etiquetas-mes de los últimos 3 meses
    now = datetime.now(timezone.utc)
    def get_month_start(offset_months: int) -> datetime:
        year = now.year
        month = now.month - offset_months
        while month <= 0:
            month += 12
            year -= 1
        # A mediados de ese mes para garantizar que create_at caiga dentro de él.
        return datetime(year, month, 15, tzinfo=timezone.utc)

    # Demanda cronológica semilla de Software: Mes 1 = 10, Mes 2 = 15, Mes 3 = 20 (Crecimiento sostenido > 20%)
    m1_date = get_month_start(2)
    m2_date = get_month_start(1)
    m3_date = get_month_start(0)

    # Insertar billetes m1
    for i in range(10):
        await db["tickets"].insert_one({
            "code": f"TK-A-{i}", "status": "Cerrado", "customer_id": orgs["risk"]["rut"],
            "categoria": "Software", "created_at": m1_date, "resuelto_at": m1_date + timedelta(hours=1)
        })
    # Insertar billetes de m2
    for i in range(15):
        await db["tickets"].insert_one({
            "code": f"TK-B-{i}", "status": "Cerrado", "customer_id": orgs["risk"]["rut"],
            "categoria": "Software", "created_at": m2_date, "resuelto_at": m2_date + timedelta(hours=1)
        })
    # Insertar billetes m3
    for i in range(20):
        await db["tickets"].insert_one({
            "code": f"TK-C-{i}", "status": "Cerrado", "customer_id": orgs["risk"]["rut"],
            "categoria": "Software", "created_at": m3_date, "resuelto_at": m3_date + timedelta(hours=1)
        })

    # Demanda cronológica plana de semilla para Redes: Mes 1 = 10, Mes 2 = 8, Mes 3 = 10 (No sostenida > 20%)
    for i in range(10):
        await db["tickets"].insert_one({
            "code": f"TK-D-{i}", "status": "Cerrado", "customer_id": orgs["risk"]["rut"],
            "categoria": "Redes", "created_at": m1_date, "resuelto_at": m1_date + timedelta(hours=1)
        })
    for i in range(8):
        await db["tickets"].insert_one({
            "code": f"TK-E-{i}", "status": "Cerrado", "customer_id": orgs["risk"]["rut"],
            "categoria": "Redes", "created_at": m2_date, "resuelto_at": m2_date + timedelta(hours=1)
        })
    for i in range(10):
        await db["tickets"].insert_one({
            "code": f"TK-F-{i}", "status": "Cerrado", "customer_id": orgs["risk"]["rut"],
            "categoria": "Redes", "created_at": m3_date, "resuelto_at": m3_date + timedelta(hours=1)
        })

    # Solicitar proyección de capacidad
    admin_token = create_access_token({"sub": "admin@techhelp.cl", "role": "Administrador"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Solicitud válida (rango_meses = 3)
        response = await ac.get("/api/v1/analytics/capacity-projection?rango_meses=3", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        # El software debe tener recomendación de alerta de contratación.
        software_proj = next(x for x in data["projections"] if x["categoria"] == "Software")
        assert software_proj["alerta"] == "Se recomienda la contratación inmediata de personal de soporte técnico"

        # Redes NO debe tener alerta
        redes_proj = next(x for x in data["projections"] if x["categoria"] == "Redes")
        assert redes_proj["alerta"] is None

        # 2. Verificación de restricción de rango fuera de límites (rango_meses < 3)
        response_bad = await ac.get("/api/v1/analytics/capacity-projection?rango_meses=2", headers=headers)
        assert response_bad.status_code == 422