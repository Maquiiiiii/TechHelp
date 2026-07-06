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
from backend.security.auth import create_access_token
from backend.routes.login import ADMIN_STATE, ADMIN_EMAIL

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
    
    # Restablecer el estado de inicio de sesión del administrador en memoria antes de cada prueba
    ADMIN_STATE[ADMIN_EMAIL] = {
        "failed_attempts": 0,
        "locked_until": None
    }
    
    # Completar previamente una organización de prueba
    await OrganizationDAO.create(
        name="TechHelp Client Org",
        rut="12345678-5",
        email="client@techhelp.cl"
    )
    
    yield
    await db[OrganizationDAO.collection_name].delete_many({})
    await db[TicketDAO.collection_name].delete_many({})
    await db[TechnicianDAO.collection_name].delete_many({})
    await db[AuditLogDAO.collection_name].delete_many({})
    Database.close_db()


# ==========================================
# 1. PRUEBAS DE FIJACIÓN (RF-006)
# ==========================================

@pytest.mark.anyio
async def test_attachment_upload_valid_file(setup_db):
    """Test attaching valid file formats (PDF, PNG, JPG) <= 5MB to a ticket."""
    ticket = await TicketDAO.create(
        title="Fallo Teclado",
        description="Fallo de teclado de contabilidad largo y detallado para superar 20 caracteres.",
        customer_id="12345678-5",
        categoria="Hardware",
        prioridad="Baja"
    )
    ticket_id = ticket["_id"]
    token = create_access_token({"sub": "client@techhelp.cl", "role": "Cliente", "organization_rut": "12345678-5"})
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Simular la carga de un PDF válido de tamaño pequeño
        files = {"file": ("documento.pdf", b"Simulated PDF content", "application/pdf")}
        response = await ac.post(f"/api/v1/tickets/{ticket_id}/attachments", files=files, headers=headers)
        
        assert response.status_code == 201
        data = response.json()
        assert len(data["adjuntos"]) == 1
        assert data["adjuntos"][0].startswith("http://localhost:8000/uploads/")
        assert data["adjuntos"][0].endswith("_documento.pdf")

@pytest.mark.anyio
async def test_attachment_upload_invalid_extension(setup_db):
    """Test uploading invalid file extensions is rejected with 400."""
    ticket = await TicketDAO.create(
        title="Fallo Teclado",
        description="Fallo de teclado de contabilidad largo y detallado para superar 20 caracteres.",
        customer_id="12345678-5",
        categoria="Hardware",
        prioridad="Baja"
    )
    ticket_id = ticket["_id"]
    token = create_access_token({"sub": "client@techhelp.cl", "role": "Cliente", "organization_rut": "12345678-5"})
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        files = {"file": ("malicious.exe", b"binary payload", "application/octet-stream")}
        response = await ac.post(f"/api/v1/tickets/{ticket_id}/attachments", files=files, headers=headers)
        assert response.status_code == 400
        assert "Formato de archivo no permitido" in response.json()["detail"]

@pytest.mark.anyio
async def test_attachment_upload_exceeds_size(setup_db):
    """Test files > 5MB are rejected with 400."""
    ticket = await TicketDAO.create(
        title="Fallo Teclado",
        description="Fallo de teclado de contabilidad largo y detallado para superar 20 caracteres.",
        customer_id="12345678-5",
        categoria="Hardware",
        prioridad="Baja"
    )
    ticket_id = ticket["_id"]
    token = create_access_token({"sub": "client@techhelp.cl", "role": "Cliente", "organization_rut": "12345678-5"})
    headers = {"Authorization": f"Bearer {token}"}

    large_content = b"x" * (5 * 1024 * 1024 + 10)  # > 5MB
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        files = {"file": ("heavy.png", large_content, "image/png")}
        response = await ac.post(f"/api/v1/tickets/{ticket_id}/attachments", files=files, headers=headers)
        assert response.status_code == 400
        assert "excede el tamaño máximo" in response.json()["detail"]


# ==========================================
# 2. COMENTARIOS Y PRUEBAS DE VISIBILIDAD (RF-017 y RF-018)
# ==========================================

@pytest.mark.anyio
async def test_comments_visibility_rules_by_role(setup_db, capsys):
    """Verify visibility rules for internal comments and console alerts (RF-017, RF-018)."""
    # Crear ticket
    ticket = await TicketDAO.create(
        title="Incidente Servidor",
        description="El servidor de base de datos arrojó timeouts recurrentes.",
        customer_id="12345678-5",
        categoria="Software",
        prioridad="Alta"
    )
    ticket_id = ticket["_id"]

    # Genera tokens para diferentes roles
    admin_token = create_access_token({"sub": "admin@techhelp.cl", "role": "Administrador"})
    tech_token = create_access_token({"sub": "tecnico@techhelp.cl", "role": "Tecnico"})
    client_token = create_access_token({"sub": "client@techhelp.cl", "role": "Cliente", "organization_rut": "12345678-5"})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Publicar un comentario interno utilizando credenciales de técnico.
        headers_tech = {"Authorization": f"Bearer {tech_token}"}
        payload_internal = {"texto": "Comentario interno técnico para auditoría", "es_interno": True}
        res_int = await ac.post(f"/api/v1/tickets/{ticket_id}/comments", json=payload_internal, headers=headers_tech)
        assert res_int.status_code == 201
        
        # 2. Publicar un comentario público utilizando credenciales de técnico.
        payload_public = {"texto": "Estimado cliente, ya estamos revisando el caso", "es_interno": False}
        res_pub = await ac.post(f"/api/v1/tickets/{ticket_id}/comments", json=payload_public, headers=headers_tech)
        assert res_pub.status_code == 201

        # Verifique la salida del disparador de alerta de la consola (RF-018)
        captured = capsys.readouterr()
        assert f"Enviando email de alerta al cliente con URL: /tickets/{ticket_id}" in captured.out

        # 3. Recuperar los detalles del ticket usando las credenciales del Cliente
        headers_client = {"Authorization": f"Bearer {client_token}"}
        res_client = await ac.get(f"/api/v1/tickets/{ticket_id}", headers=headers_client)
        assert res_client.status_code == 200
        data_client = res_client.json()
        # Afirma que los comentarios internos están estrictamente ocultos para los clientes (RF-017)
        comments_client = data_client["comentarios"]
        assert len(comments_client) == 1
        assert comments_client[0]["texto"] == "Estimado cliente, ya estamos revisando el caso"
        assert comments_client[0]["es_interno"] is False

        # 4. Recupere los detalles del ticket usando las credenciales de administrador
        headers_admin = {"Authorization": f"Bearer {admin_token}"}
        res_admin = await ac.get(f"/api/v1/tickets/{ticket_id}", headers=headers_admin)
        assert res_admin.status_code == 200
        data_admin = res_admin.json()
        # El administrador de afirmaciones y ambos comentarios.
        comments_admin = data_admin["comentarios"]
        assert len(comments_admin) == 2


# ==========================================
# 3. PRUEBAS DE INICIO DE SESIÓN TOTP DE MFA (RF-021)
# ==========================================

@pytest.mark.anyio
async def test_mfa_login_flow_success(setup_db):
    """Test 2-step MFA login flow happy path."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Paso 1: Credenciales
        payload_s1 = {"email": "admin@techhelp.cl", "password": "admin123"}
        res_s1 = await ac.post("/api/v1/login/step1", json=payload_s1)
        assert res_s1.status_code == 200
        data_s1 = res_s1.json()
        assert data_s1["mfa_required"] is True
        temp_token = data_s1["temp_token"]

        # Paso 2: OTP válida (¡cualquier código! = '000000')
        payload_s2 = {"temp_token": temp_token, "code": "123456"}
        res_s2 = await ac.post("/api/v1/login/step2", json=payload_s2)
        assert res_s2.status_code == 200
        data_s2 = res_s2.json()
        assert "access_token" in data_s2
        assert data_s2["token_type"] == "bearer"

@pytest.mark.anyio
async def test_mfa_login_fails_and_locks(setup_db):
    """Test that 3 consecutive incorrect OTP submissions lock the account."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Obtenga el token temporal del Paso 1
        res_s1 = await ac.post("/api/v1/login/step1", json={"email": "admin@techhelp.cl", "password": "admin123"})
        temp_token = res_s1.json()["temp_token"]

        # OTP incorrecta: '000000'
        payload_s2 = {"temp_token": temp_token, "code": "000000"}

        # intención 1
        res1 = await ac.post("/api/v1/login/step2", json=payload_s2)
        assert res1.status_code == 401

        # intención 2
        res2 = await ac.post("/api/v1/login/step2", json=payload_s2)
        assert res2.status_code == 401

        # Intento 3: bloqueo de cuenta activada
        res3 = await ac.post("/api/v1/login/step2", json=payload_s2)
        assert res3.status_code == 403
        assert "bloqueada temporalmente" in res3.json()["detail"]

        # Verifique que el paso 1 esté bloqueado ahora
        res_blocked = await ac.post("/api/v1/login/step1", json={"email": "admin@techhelp.cl", "password": "admin123"})
        assert res_blocked.status_code == 403