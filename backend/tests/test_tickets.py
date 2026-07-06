import os
import pytest
from httpx import AsyncClient, ASGITransport
from pydantic import ValidationError

# Forzar la prueba del URI de la base de datos antes de las importaciones
os.environ["MONGO_URI"] = "mongodb://localhost:27017/techhelp_test_db"

from backend.main import app
from backend.config.database import Database
from backend.dao.organization_dao import OrganizationDAO
from backend.dao.ticket_dao import TicketDAO
from backend.dto.ticket_dto import TicketCreateDTO
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
    
    # Complete previamente una organización de prueba (necesaria para la verificación de verificación del cliente RF-002)
    await OrganizationDAO.create(
        name="TechHelp Client Org",
        rut="12345678-5",
        email="client@techhelp.cl"
    )
    
    yield
    await db[OrganizationDAO.collection_name].delete_many({})
    await db[TicketDAO.collection_name].delete_many({})
    Database.close_db()


# ==========================================
# 1. PRUEBAS DE VALIDACIÓN DE BILLETES DTO
# ==========================================

def test_ticket_dto_valid():
    """Verify that a valid ticket schema definition loads correctly."""
    dto = TicketCreateDTO(
        title="Error de red",
        description="El router del segundo piso del edificio A se desconecta constantemente interrumpiendo el flujo.",
        customer_id="12.345.678-5",
        categoria="Redes",
        prioridad="Alta"
    )
    assert dto.title == "Error de red"
    assert dto.customer_id == "12345678-5"  # RUT normalizado
    assert len(dto.description) >= 20
    assert dto.prioridad == "Alta"

def test_ticket_dto_short_description():
    """Verify that description lengths below 20 characters are rejected (RF-005)."""
    with pytest.raises(ValidationError) as excinfo:
        TicketCreateDTO(
            title="Soporte Técnico",
            description="Demasiado corto",  # 15 caracteres
            customer_id="12.345.678-5",
            categoria="Hardware",
            prioridad="Baja"
        )
    assert "at least 20 characters" in str(excinfo.value) or "string_too_short" in str(excinfo.value)

def test_ticket_dto_invalid_priority():
    """Verify that priorities outside the allowed values list are rejected."""
    with pytest.raises(ValidationError):
        TicketCreateDTO(
            title="Soporte Técnico",
            description="El cargador de la laptop corporativa no entrega energía.",
            customer_id="12.345.678-5",
            categoria="Hardware",
            prioridad="Urgente"  # Literal de prioridad no válido
        )


# ==========================================
# 2. PRUEBAS DE TRANSICIONES Y PUNTOS FINALES DEL BOLETO
# ==========================================

@pytest.mark.anyio
async def test_api_create_ticket_success(setup_db):
    """Test successful ticket registration through HTTP API."""
    token = create_access_token({"sub": "client@techhelp.cl", "role": "Cliente", "organization_rut": "12345678-5"})
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "title": "Fallo de Impresora",
            "description": "La impresora láser de contabilidad está atascada y arroja error 50.4.",
            "customer_id": "12.345.678-5",
            "categoria": "Hardware",
            "prioridad": "Media"
        }
        response = await ac.post("/api/v1/tickets", json=payload, headers=headers)
        assert response.status_code == 201
        data = response.json()
        
        assert "_id" in data
        assert "code" in data
        assert data["code"].startswith("TK-")
        assert len(data["code"]) == 8  # TK-XXXXX (8 caracteres)
        assert data["status"] == "Abierto"
        assert data["customer_id"] == "12345678-5"
        assert data["__v"] == 0

@pytest.mark.anyio
async def test_api_create_ticket_invalid_client(setup_db):
    """Test that creating a ticket for a non-existing customer organization fails (RF-002)."""
    admin_token = create_access_token({"sub": "admin@techhelp.cl", "role": "Administrador"})
    headers = {"Authorization": f"Bearer {admin_token}"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "title": "Fallo de Impresora",
            "description": "La impresora láser de contabilidad está atascada y arroja error 50.4.",
            "customer_id": "11.111.111-1",  # La organización no existe.
            "categoria": "Hardware",
            "prioridad": "Media"
        }
        response = await ac.post("/api/v1/tickets", json=payload, headers=headers)
        assert response.status_code == 404
        assert "no existe" in response.json()["error"]

@pytest.mark.anyio
async def test_ticket_state_machine_illegal_skips(setup_db):
    """Verify that moving directly from Abierto to En Proceso is blocked (RF-007)."""
    # 1. Crea un billete
    ticket = await TicketDAO.create(
        title="Incidente VPN",
        description="El cliente de VPN corporativo desconecta las sesiones remotas tras 15 minutos.",
        customer_id="12.345.678-5",
        categoria="Redes",
        prioridad="Alta"
    )
    ticket_id = ticket["_id"]
    version = ticket["__v"]
    
    admin_token = create_access_token({"sub": "admin@techhelp.cl", "role": "Administrador"})
    headers = {"Authorization": f"Bearer {admin_token}"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 2. Intentar actualización ilegal (Abierto -> En Proceso) directamente
        payload = {
            "status": "En Proceso",
            "version": version
        }
        response = await ac.put(f"/api/v1/tickets/{ticket_id}/status", json=payload, headers=headers)
        assert response.status_code == 400
        assert "Transición ilegal" in response.json()["error"]

@pytest.mark.anyio
async def test_ticket_state_machine_happy_path(setup_db):
    """Verify standard transition chain: Abierto -> Asignado -> En Proceso -> En Espera -> En Proceso -> Resuelto -> Cerrado."""
    ticket = await TicketDAO.create(
        title="Incidente VPN",
        description="El cliente de VPN corporativo desconecta las sesiones remotas tras 15 minutos.",
        customer_id="12.345.678-5",
        categoria="Redes",
        prioridad="Alta"
    )
    ticket_id = ticket["_id"]
    v = ticket["__v"]

    admin_token = create_access_token({"sub": "admin@techhelp.cl", "role": "Administrador"})
    headers = {"Authorization": f"Bearer {admin_token}"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Abierto -> Asignado (OK)
        res1 = await ac.put(f"/api/v1/tickets/{ticket_id}/status", json={"status": "Asignado", "version": v}, headers=headers)
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["status"] == "Asignado"
        v = data1["__v"]

        # 2. Asignado -> En Proceso (OK). Debe escribir en_proceso_at UTC.
        res2 = await ac.put(f"/api/v1/tickets/{ticket_id}/status", json={"status": "En Proceso", "version": v}, headers=headers)
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["status"] == "En Proceso"
        assert data2["en_proceso_at"] is not None  # Marca de tiempo UTC (RF-007)
        v = data2["__v"]

        # 3. En Proceso -> En Espera (Falla sin justificación de pausas - RF-010)
        res3_fail = await ac.put(f"/api/v1/tickets/{ticket_id}/status", json={"status": "En Espera", "version": v}, headers=headers)
        assert res3_fail.status_code == 422  # Error de validación (campo faltante)
        
        # En Proceso -> En Espera (OK con justificación)
        res3 = await ac.put(f"/api/v1/tickets/{ticket_id}/status", json={
            "status": "En Espera",
            "version": v,
            "justificacion_pausa": "Esperando repuestos de tarjeta de red del proveedor."
        }, headers=headers)
        assert res3.status_code == 200
        data3 = res3.json()
        assert data3["status"] == "En Espera"
        assert data3["justificacion_pausa"] == "Esperando repuestos de tarjeta de red del proveedor."
        v = data3["__v"]

        # 4. En Espera -> En Proceso (OK)
        res4 = await ac.put(f"/api/v1/tickets/{ticket_id}/status", json={"status": "En Proceso", "version": v}, headers=headers)
        assert res4.status_code == 200
        data4 = res4.json()
        assert data4["status"] == "En Proceso"
        v = data4["__v"]

        # 5. En Proceso -> Resuelto (Falla sin comentario de solución - RF-008)
        res5_fail = await ac.put(f"/api/v1/tickets/{ticket_id}/status", json={"status": "Resuelto", "version": v}, headers=headers)
        assert res5_fail.status_code == 422
        
        # En Proceso -> Resuelto (OK con comentario)
        res5 = await ac.put(f"/api/v1/tickets/{ticket_id}/status", json={
            "status": "Resuelto",
            "version": v,
            "comentario_solucion": "Se reconfiguró el tiempo de sesión máximo en la VPN de 15 a 120 minutos."
        }, headers=headers)
        assert res5.status_code == 200
        data5 = res5.json()
        assert data5["status"] == "Resuelto"
        assert data5["comentario_solucion"] == "Se reconfiguró el tiempo de sesión máximo en la VPN de 15 a 120 minutos."
        v = data5["__v"]

        # 6. Resuelto -> Cerrado (OK)
        res6 = await ac.put(f"/api/v1/tickets/{ticket_id}/status", json={"status": "Cerrado", "version": v}, headers=headers)
        assert res6.status_code == 200
        assert res6.json()["status"] == "Cerrado"

@pytest.mark.anyio
async def test_ticket_occ_lock_failure(setup_db):
    """Test that modifying a ticket with an outdated version raises a 409 conflict."""
    ticket = await TicketDAO.create(
        title="Incidente Hardware",
        description="La pantalla del monitor parpadea constantemente al encender el equipo de oficina.",
        customer_id="12.345.678-5",
        categoria="Hardware",
        prioridad="Baja"
    )
    ticket_id = ticket["_id"]
    version = ticket["__v"]

    admin_token = create_access_token({"sub": "admin@techhelp.cl", "role": "Administrador"})
    headers = {"Authorization": f"Bearer {admin_token}"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Primera actualización cambia de estado a Asignado
        res1 = await ac.put(f"/api/v1/tickets/{ticket_id}/status", json={"status": "Asignado", "version": version}, headers=headers)
        assert res1.status_code == 200
        
        # La segunda actualización utiliza una versión desactualizada (0 en lugar de 1)
        res2 = await ac.put(f"/api/v1/tickets/{ticket_id}/status", json={"status": "En Proceso", "version": 0}, headers=headers)
        assert res2.status_code == 409
        assert "concurrencia" in res2.json()["error"]

@pytest.mark.anyio
async def test_client_cannot_spoof_rut(setup_db):
    """Verify client cannot submit a spoofed RUT. It gets overwritten with the JWT organization_rut."""
    token = create_access_token({"sub": "client@techhelp.cl", "role": "Cliente", "organization_rut": "12345678-5"})
    headers = {"Authorization": f"Bearer {token}"}
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "title": "Fallo de Impresora",
            "description": "La impresora láser de contabilidad está atascada y arroja error 50.4.",
            "customer_id": "99999999-9",  # PRU falsificado
            "categoria": "Hardware",
            "prioridad": "Media"
        }
        response = await ac.post("/api/v1/tickets", json=payload, headers=headers)
        assert response.status_code == 201
        data = response.json()
        assert data["customer_id"] == "12345678-5" # Sobrescrito de forma segura

@pytest.mark.anyio
async def test_client_multi_tenant_isolation(setup_db):
    """Verify that a client cannot get nor list tickets belonging to other organizations."""
    # Crear ticket para la organización A (12345678-5)
    ticket_org_a = await TicketDAO.create(
        title="VPN Issue Org A",
        description="Unable to connect to VPN for organization A.",
        customer_id="12345678-5",
        categoria="Redes",
        prioridad="Alta"
    )
    
    # Crear una organizacion de prueba secundaria B
    await OrganizationDAO.create(
        name="Org B",
        rut="23456789-6",
        email="client@orgb.cl"
    )
    ticket_org_b = await TicketDAO.create(
        title="Hardware Issue Org B",
        description="Printer offline for organization B employees.",
        customer_id="23456789-6",
        categoria="Hardware",
        prioridad="Media"
    )

    # Cliente del token Org A
    token_a = create_access_token({"sub": "client@techhelp.cl", "role": "Cliente", "organization_rut": "12345678-5"})
    headers_a = {"Authorization": f"Bearer {token_a}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # OBTÉN boleto único Org A (Éxito)
        res_get_a = await ac.get(f"/api/v1/tickets/{ticket_org_a['_id']}", headers=headers_a)
        assert res_get_a.status_code == 200
        
        # OBTENER boleto sencillo Org B (Rechazado - 404/403)
        res_get_b = await ac.get(f"/api/v1/tickets/{ticket_org_b['_id']}", headers=headers_a)
        assert res_get_b.status_code in [403, 404]

        # LISTA de boletos (solo debe devolver boletos de la Org A)
        res_list = await ac.get("/api/v1/tickets", headers=headers_a)
        assert res_list.status_code == 200
        list_data = res_list.json()
        for t in list_data:
            assert t["customer_id"] == "12345678-5"

@pytest.mark.anyio
async def test_client_status_modification_restrictions(setup_db):
    """Verify that a client can only transition a ticket to 'Cancelado' or 'Resuelto'."""
    ticket = await TicketDAO.create(
        title="Router Issue Org A",
        description="Router is completely dead in floor 3 office.",
        customer_id="12345678-5",
        categoria="Redes",
        prioridad="Alta"
    )
    ticket_id = ticket["_id"]
    
    token = create_access_token({"sub": "client@techhelp.cl", "role": "Cliente", "organization_rut": "12345678-5"})
    headers = {"Authorization": f"Bearer {token}"}
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # El cliente intenta realizar la transición a Asignado (cambio de estado prohibido: 400 solicitud incorrecta)
        res_illegal = await ac.put(f"/api/v1/tickets/{ticket_id}/status", json={"status": "Asignado", "version": 0}, headers=headers)
        assert res_illegal.status_code == 400
        
        # Cliente cambia a Cancelado (Éxito)
        res_cancel = await ac.put(f"/api/v1/tickets/{ticket_id}/status", json={"status": "Cancelado", "version": 0}, headers=headers)
        assert res_cancel.status_code == 200
        assert res_cancel.json()["status"] == "Cancelado"

@pytest.mark.anyio
async def test_client_auto_assign_and_technician_modification_blocked(setup_db):
    """Verify that clients are strictly forbidden from calling auto-assign or modifying technician fields."""
    ticket = await TicketDAO.create(
        title="Router Issue Org A",
        description="Router is completely dead in floor 3 office.",
        customer_id="12345678-5",
        categoria="Redes",
        prioridad="Alta"
    )
    ticket_id = ticket["_id"]
    
    token = create_access_token({"sub": "client@techhelp.cl", "role": "Cliente", "organization_rut": "12345678-5"})
    headers = {"Authorization": f"Bearer {token}"}
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Publicar para asignar automáticamente el punto final (Prohibido - 403)
        res_assign = await ac.post(f"/api/v1/tickets/{ticket_id}/auto-assign", json={"version": 0}, headers=headers)
        assert res_assign.status_code == 403
        
        # Intento de modificar el estado mientras se inyecta el campo técnico_id (Prohibido - 403)
        res_inject = await ac.put(f"/api/v1/tickets/{ticket_id}/status", json={
            "status": "Cancelado",
            "version": 0,
            "technician_id": "tech_hacker_123"
        }, headers=headers)
        assert res_inject.status_code == 403