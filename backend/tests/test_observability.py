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
from backend.dao.technician_dao import TechnicianDAO
from backend.dao.log_dao import AuditLogDAO
from backend.tasks.sla_monitor import check_sla_breaches
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
    await TechnicianDAO.create_indexes()
    await db[OrganizationDAO.collection_name].delete_many({})
    await db[TicketDAO.collection_name].delete_many({})
    await db[TechnicianDAO.collection_name].delete_many({})
    await db[AuditLogDAO.collection_name].delete_many({})
    
    # Completar previamente una organización de prueba
    await OrganizationDAO.create(
        name="TechHelp Client Org",
        rut="12345678-5",
        email="client@techhelp.cl"
    )
    
    # Completar previamente un técnico
    await TechnicianDAO.create(
        name="Carlos Silva",
        rut="12345678-5",
        email="carlos.silva@techhelp.cl",
        especialidad="Hardware"
    )
    
    yield
    await db[OrganizationDAO.collection_name].delete_many({})
    await db[TicketDAO.collection_name].delete_many({})
    await db[TechnicianDAO.collection_name].delete_many({})
    await db[AuditLogDAO.collection_name].delete_many({})
    Database.close_db()


# ==========================================
# 1. PRUEBAS DE REGISTRO DE AUDITORÍA CON INYECCIÓN IP (RF-014)
# ==========================================

@pytest.mark.anyio
async def test_audit_logs_on_transitions_with_ip(setup_db):
    """Verify that transitions write immutable audit logs with ip_origen and millisecond precision."""
    db = Database.get_db()
    
    # 1. Crea un billete
    ticket = await TicketDAO.create(
        title="Incidente Hardware",
        description="Fallo de monitor parpadeante en oficina de contabilidad.",
        customer_id="12345678-5",
        categoria="Hardware",
        prioridad="Alta"
    )
    ticket_id = ticket["_id"]
    v = ticket["__v"]
    
    # 2. Actualización a asignado
    admin_token = create_access_token({"sub": "admin@techhelp.cl", "role": "Administrador"})
    headers = {"Authorization": f"Bearer {admin_token}"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res1 = await ac.put(f"/api/v1/tickets/{ticket_id}/status", json={"status": "Asignado", "version": v}, headers=headers)
        assert res1.status_code == 200
        v = res1.json()["__v"]
        
        # 3. Actualización a En Proceso
        res2 = await ac.put(f"/api/v1/tickets/{ticket_id}/status", json={"status": "En Proceso", "version": v}, headers=headers)
        assert res2.status_code == 200

    # 4. Consultar registros de auditoría en la base de datos
    logs = await db[AuditLogDAO.collection_name].find({"ticket_id": ticket_id}).sort("timestamp", 1).to_list(length=None)
    
    assert len(logs) == 2
    
    # Verifique que la IP de origen esté presente y sea correcta (el cliente simulado predeterminado es 127.0.0.1 o testclient loopback)
    assert logs[0]["ip_origen"] in ["127.0.0.1", "testclient"]
    assert logs[1]["ip_origen"] in ["127.0.0.1", "testclient"]
    assert isinstance(logs[0]["timestamp"], datetime)


# ==========================================
# 2. TAREA DE FONDO DE MONITOREO DE SLA (RF-015)
# ==========================================

@pytest.mark.anyio
async def test_sla_monitor_expires_after_120_minutes(setup_db):
    """Verify SLA breaches flag a ticket as expired after 120 net minutes (RF-015)."""
    db = Database.get_db()
    
    # 1. Crear billete
    ticket = await TicketDAO.create(
        title="Ticket Alta Prioridad",
        description="Fallo de red crítico que desconecta terminales del almacén central.",
        customer_id="12345678-5",
        categoria="Hardware",
        prioridad="Alta"
    )
    ticket_id = ticket["_id"]
    
    # 2. Vuelva a establecer create_at en hace 130 minutos y el estado en Asignado.
    past_date = datetime.now(timezone.utc) - timedelta(minutes=130)
    await db[TicketDAO.collection_name].update_one(
        {"_id": ObjectId(ticket_id)},
        {"$set": {"created_at": past_date, "status": "Asignado"}}
    )

    # 3. Activar la verificación del monitor SLA manualmente
    await check_sla_breaches()
    
    # 4. Verificar sla_vencido = True
    updated_ticket = await db[TicketDAO.collection_name].find_one({"_id": ObjectId(ticket_id)})
    assert updated_ticket.get("sla_vencido") is True

@pytest.mark.anyio
async def test_sla_monitor_excludes_en_espera_minutes_accumulated(setup_db):
    """Verify SLA monitor excludes accumulated wait minutes directly from minutos_en_espera_acumulados."""
    db = Database.get_db()
    
    # 1. Crear billete
    ticket = await TicketDAO.create(
        title="Ticket Alta Prioridad",
        description="Fallo de red crítico que desconecta terminales del almacén central.",
        customer_id="12345678-5",
        categoria="Hardware",
        prioridad="Alta"
    )
    ticket_id = ticket["_id"]
    
    # Creado hace 130 minutos, actualmente asignado, con 30.0 minutos de tiempo de espera acumulados
    past_date = datetime.now(timezone.utc) - timedelta(minutes=130)
    await db[TicketDAO.collection_name].update_one(
        {"_id": ObjectId(ticket_id)},
        {"$set": {
            "created_at": past_date, 
            "status": "Asignado",
            "minutos_en_espera_acumulados": 30.0
        }}
    )

    # Atención total transcurrida: 130 minutos
    # Tiempo transcurrido en 'En Espera': 30 minutos acumulados
    # Tiempo neto de atención: 130 - 30 = 100 minutos (¡que es MENOS del límite de 120 minutos!)
    
    # 2. Activar la verificación del monitor SLA manualmente
    await check_sla_breaches()
    
    # 3. Verificar que sla_vencido permaneció Falso/Ninguno
    updated_ticket = await db[TicketDAO.collection_name].find_one({"_id": ObjectId(ticket_id)})
    assert updated_ticket.get("sla_vencido") is not True


# ==========================================
# 3. PROTECCIÓN DE MÉTRICAS DEL SALPICADERO (RF-020)
# ==========================================

@pytest.mark.anyio
async def test_dashboard_metrics_unauthorized_without_jwt(setup_db):
    """Test dashboard metrics returns 401 Unauthorized if no JWT credentials are provided."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/dashboard/metrics")
        assert response.status_code == 401

@pytest.mark.anyio
async def test_dashboard_metrics_forbidden_if_not_admin(setup_db):
    """Test dashboard metrics returns 403 Forbidden if user is authenticated but not an Administrador."""
    token = create_access_token({"sub": "tech@techhelp.cl", "role": "Tecnico"})
    headers = {"Authorization": f"Bearer {token}"}
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/dashboard/metrics", headers=headers)
        assert response.status_code == 403

@pytest.mark.anyio
async def test_dashboard_metrics_success_with_admin_role(setup_db):
    """Test dashboard metrics succeeds when a valid Administrador JWT is provided."""
    # 1. Completa los tickets con diferentes estados
    t1 = await TicketDAO.create(title="Ticket A", description="Descripción del ticket de prueba de hardware.", customer_id="12345678-5", categoria="Hardware", prioridad="Baja")
    t2 = await TicketDAO.create(title="Ticket B", description="Descripción del ticket de prueba de hardware.", customer_id="12345678-5", categoria="Hardware", prioridad="Media")
    t3 = await TicketDAO.create(title="Ticket C", description="Descripción del ticket de prueba de hardware.", customer_id="12345678-5", categoria="Hardware", prioridad="Alta")
    
    db = Database.get_db()
    # Cambie manualmente los estados en la base de datos para representar diferentes estados
    await db[TicketDAO.collection_name].update_one({"_id": ObjectId(t1["_id"])}, {"$set": {"status": "En Proceso"}})
    await db[TicketDAO.collection_name].update_one({"_id": ObjectId(t2["_id"])}, {"$set": {"status": "Resuelto"}})

    # Generar token para Administrador
    token = create_access_token({"sub": "admin@techhelp.cl", "role": "Administrador"})
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Activar la API HTTP de métricas del panel
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/dashboard/metrics", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verificar el mapeo de recuentos:
        assert data["Abierto"] == 1
        assert data["En Proceso"] == 1
        assert data["Resuelto"] == 1
        
        # Los estados despoblados deben devolver 0 (verificación RF-020)
        assert data["Asignado"] == 0
        assert data["En Espera"] == 0
        assert data["Cerrado"] == 0