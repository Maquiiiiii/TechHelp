import os
import pytest
from httpx import AsyncClient, ASGITransport
from pydantic import ValidationError
from bson import ObjectId
from datetime import datetime, timezone, timedelta

# Forzar la prueba del URI de la base de datos antes de las importaciones
os.environ["MONGO_URI"] = "mongodb://localhost:27017/techhelp_test_db"

from backend.main import app
from backend.config.database import Database
from backend.dao.organization_dao import OrganizationDAO
from backend.dao.ticket_dao import TicketDAO
from backend.dao.technician_dao import TechnicianDAO
from backend.dto.technician_dto import TechnicianCreateDTO
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
    await db["counters"].delete_many({})  # Restablecer contadores de incremento automático
    
    # Complete previamente una organización de prueba (necesaria para la verificación de verificación del cliente)
    await OrganizationDAO.create(
        name="TechHelp Client Org",
        rut="12345678-5",
        email="client@techhelp.cl"
    )
    
    yield
    await db[OrganizationDAO.collection_name].delete_many({})
    await db[TicketDAO.collection_name].delete_many({})
    await db[TechnicianDAO.collection_name].delete_many({})
    await db["counters"].delete_many({})
    Database.close_db()


# ==========================================
# 1. PRUEBAS DE VALIDACIÓN DEL TÉCNICO DTO
# ==========================================

def test_technician_dto_valid():
    """Verify that a valid technician schema definition loads correctly."""
    dto = TechnicianCreateDTO(
        name="Carlos Silva",
        rut="12.345.678-5",
        email="carlos.silva@techhelp.cl",
        especialidad="Hardware"
    )
    assert dto.name == "Carlos Silva"
    assert dto.rut == "12345678-5"  # Verificar normalización
    assert dto.especialidad == "Hardware"

def test_technician_dto_invalid_rut():
    """Verify that an invalid Chilean RUT is rejected by the DTO."""
    with pytest.raises(ValidationError):
        TechnicianCreateDTO(
            name="Carlos Silva",
            rut="12.345.678-9",  # Verificador de dígitos no válidos
            email="carlos.silva@techhelp.cl",
            especialidad="Software"
        )


# ==========================================
# 2. PRUEBAS DE PUNTO FINAL DE API TÉCNICO
# ==========================================

@pytest.mark.anyio
async def test_api_create_technician_success(setup_db):
    """Test successful technician registration with autoincremental sequential ID (RF-003)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Crear tecnología 1
        payload_1 = {
            "name": "Andrés Gómez",
            "rut": "12.345.678-5",
            "email": "andres.gomez@techhelp.cl",
            "especialidad": "Hardware"
        }
        response_1 = await ac.post("/api/v1/technicians", json=payload_1)
        assert response_1.status_code == 201
        data_1 = response_1.json()
        assert data_1["tech_id"] == 1  # ID secuencial a partir de 1
        assert data_1["status"] == "Disponible"
        
        # Crear tecnología 2
        payload_2 = {
            "name": "Beatriz Soto",
            "rut": "11.111.111-1",
            "email": "beatriz.soto@techhelp.cl",
            "especialidad": "Software"
        }
        response_2 = await ac.post("/api/v1/technicians", json=payload_2)
        assert response_2.status_code == 201
        data_2 = response_2.json()
        assert data_2["tech_id"] == 2  # ID secuencial incrementado a 2

@pytest.mark.anyio
async def test_api_create_technician_duplicate_conflict(setup_db):
    """Test that duplicate technician RUT or Email returns 409 Conflict."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload_1 = {
            "name": "Andrés Gómez",
            "rut": "12.345.678-5",
            "email": "andres.gomez@techhelp.cl",
            "especialidad": "Hardware"
        }
        res1 = await ac.post("/api/v1/technicians", json=payload_1)
        assert res1.status_code == 201

        payload_2 = {
            "name": "Andrés Copia",
            "rut": "12.345.678-5",
            "email": "copia.gomez@techhelp.cl",
            "especialidad": "Hardware"
        }
        res2 = await ac.post("/api/v1/technicians", json=payload_2)
        assert res2.status_code == 409

@pytest.mark.anyio
async def test_api_update_technician_status(setup_db):
    """Test updating technician availability status with OCC verification."""
    tech = await TechnicianDAO.create(
        name="Patricio Ruiz",
        rut="12.345.678-5",
        email="patricio.ruiz@techhelp.cl",
        especialidad="Software"
    )
    tech_id = tech["_id"]
    version = tech["__v"]
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res1 = await ac.put(f"/api/v1/technicians/{tech_id}/status", json={"status": "En Terreno", "version": version})
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["status"] == "En Terreno"
        assert data1["__v"] == 1
        
        res2 = await ac.put(f"/api/v1/technicians/{tech_id}/status", json={"status": "Licencia", "version": 0})
        assert res2.status_code == 409


# ==========================================
# 3. CARGA DE TRABAJO DE AUTOASIGNACIÓN Y DESempate (RF-013)
# ==========================================

@pytest.mark.anyio
async def test_weighted_auto_assignment_logic(setup_db):
    """
    Test workload auto-assignment algorithm (RF-013):
    - Setup 3 Available technicians with specialty 'Hardware'.
    - Setup workloads:
      * Tech A: 0 active tickets (Workload = 0)
      * Tech B: 1 Baja ticket (Workload = 1)
      * Tech C: 1 Alta ticket (Workload = 3)
    - Verify Auto-assign selects Tech A (workload 0).
    - Tech A's workload increases to 2 (Media ticket assigned).
    - Next Auto-assign selects Tech B (workload 1).
    """
    db = Database.get_db()
    
    # 1. Cree tres técnicos disponibles en la base de datos con especialidad 'Hardware'
    tech_a = await TechnicianDAO.create(name="Técnico A", rut="12.345.678-5", email="tech.a@techhelp.cl", especialidad="Hardware")
    tech_b = await TechnicianDAO.create(name="Técnico B", rut="11.111.111-1", email="tech.b@techhelp.cl", especialidad="Hardware")
    tech_c = await TechnicianDAO.create(name="Técnico C", rut="76.234.345-2", email="tech.c@techhelp.cl", especialidad="Hardware")

    # 2. Asignar previamente tickets activos para crear cargas de trabajo
    # Asigne 1 boleto de Baja a Tech B (puntuación de carga de trabajo = 1)
    ticket_baja_b = await TicketDAO.create(
        title="Teclado averiado",
        description="El teclado de contabilidad no escribe las teclas numéricas correctamente.",
        customer_id="12345678-5",
        categoria="Hardware",
        prioridad="Baja"
    )
    await TicketDAO.update_status(ticket_baja_b["_id"], ticket_baja_b["__v"], "Asignado")
    await db[TicketDAO.collection_name].update_one(
        {"_id": ObjectId(ticket_baja_b["_id"])},
        {"$set": {"assigned_tech_id": tech_b["_id"], "assigned_tech_name": tech_b["name"]}}
    )

    # Asigne 1 ticket de Alta a Tech C (puntuación de carga de trabajo = 3)
    ticket_alta_c = await TicketDAO.create(
        title="Fallo Servidor DHCP",
        description="Los terminales del centro de distribución no obtienen dirección IP para operar.",
        customer_id="12345678-5",
        categoria="Hardware",
        prioridad="Alta"
    )
    await TicketDAO.update_status(ticket_alta_c["_id"], ticket_alta_c["__v"], "Asignado")
    await db[TicketDAO.collection_name].update_one(
        {"_id": ObjectId(ticket_alta_c["_id"])},
        {"$set": {"assigned_tech_id": tech_c["_id"], "assigned_tech_name": tech_c["name"]}}
    )

    # 3. Cree un nuevo Ticket en estado Abierto (para ser asignado) en la categoría 'Hardware'
    new_ticket_1 = await TicketDAO.create(
        title="Problema de Correo",
        description="El gerente general no puede sincronizar carpetas en su cliente de correo.",
        customer_id="12345678-5",
        categoria="Hardware",  # Coincide con la especialidad 'Hardware'
        prioridad="Media" # Pesos = 2
    )

    # 4. Activar la asignación automática para new_ticket_1
    admin_token = create_access_token({"sub": "admin@techhelp.cl", "role": "Administrador"})
    headers = {"Authorization": f"Bearer {admin_token}"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res1 = await ac.post(f"/api/v1/tickets/{new_ticket_1['_id']}/auto-assign", json={"version": new_ticket_1["__v"]}, headers=headers)
        assert res1.status_code == 200
        assigned_data_1 = res1.json()
        
        # ¡Se debe elegir la tecnología A (carga de trabajo 0)!
        assert assigned_data_1["status"] == "Asignado"
        assert assigned_data_1["assigned_tech_id"] == tech_a["_id"]
        assert assigned_data_1["assigned_tech_name"] == "Técnico A"

    # 5. Crear un segundo Ticket nuevo (a asignar)
    new_ticket_2 = await TicketDAO.create(
        title="Fallo Monitor",
        description="La pantalla del monitor parpadea constantemente al encender el equipo.",
        customer_id="12345678-5",
        categoria="Hardware",
        prioridad="Media" # Pesos = 2
    )

    # 6. Activar la asignación automática para new_ticket_2
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res2 = await ac.post(f"/api/v1/tickets/{new_ticket_2['_id']}/auto-assign", json={"version": new_ticket_2["__v"]}, headers=headers)
        assert res2.status_code == 200
        assigned_data_2 = res2.json()
        
        # Tech B (carga de trabajo 1) ahora tiene el puntaje de carga de trabajo más bajo, ¡por lo que deben ser elegidos!
        assert assigned_data_2["status"] == "Asignado"
        assert assigned_data_2["assigned_tech_id"] == tech_b["_id"]
        assert assigned_data_2["assigned_tech_name"] == "Técnico B"

@pytest.mark.anyio
async def test_auto_assignment_excludes_en_espera(setup_db):
    """
    Verify workload auto-assignment calculations omit tickets in 'En Espera' status.
    - Tech A has 1 Media ticket assigned, status is 'En Espera' (Active points = 0 since En Espera is excluded).
    - Tech B has 1 Baja ticket assigned, status is 'Asignado' (Active points = 1).
    - Verify Auto-assign selects Tech A because their workload score (0) is lower than Tech B's (1).
    """
    db = Database.get_db()
    tech_a = await TechnicianDAO.create(name="Técnico A", rut="12.345.678-5", email="tech.a@techhelp.cl", especialidad="Hardware")
    tech_b = await TechnicianDAO.create(name="Técnico B", rut="11.111.111-1", email="tech.b@techhelp.cl", especialidad="Hardware")

    # Ticket 1 (Medio = 2) en estado 'En Espera' asignado al Técnico A
    ticket_a = await TicketDAO.create(
        title="Ticket A",
        description="Ticket de prueba de redes inalámbricas corporativas largas y extensas.",
        customer_id="12345678-5",
        categoria="Hardware",
        prioridad="Media"
    )
    # Establecer estado en En Espera
    await db[TicketDAO.collection_name].update_one(
        {"_id": ObjectId(ticket_a["_id"])},
        {"$set": {
            "status": "En Espera",
            "assigned_tech_id": tech_a["_id"],
            "assigned_tech_name": tech_a["name"]
        }}
    )

    # Ticket 2 (Baja = 1) en estado 'Asignado' asignado al Técnico B
    ticket_b = await TicketDAO.create(
        title="Ticket B",
        description="Ticket de prueba de redes inalámbricas corporativas largas y extensas.",
        customer_id="12345678-5",
        categoria="Hardware",
        prioridad="Baja"
    )
    await db[TicketDAO.collection_name].update_one(
        {"_id": ObjectId(ticket_b["_id"])},
        {"$set": {
            "status": "Asignado",
            "assigned_tech_id": tech_b["_id"],
            "assigned_tech_name": tech_b["name"]
        }}
    )

    # Crear nuevo ticket para autoasignar
    new_ticket = await TicketDAO.create(
        title="Nuevo Ticket",
        description="Ticket de prueba de redes inalámbricas corporativas largas y extensas.",
        customer_id="12345678-5",
        categoria="Hardware",
        prioridad="Alta"
    )

    # Activar asignación automática
    admin_token = create_access_token({"sub": "admin@techhelp.cl", "role": "Administrador"})
    headers = {"Authorization": f"Bearer {admin_token}"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(f"/api/v1/tickets/{new_ticket['_id']}/auto-assign", json={"version": new_ticket["__v"]}, headers=headers)
        assert res.status_code == 200
        data = res.json()
        # Se debe elegir el Técnico A porque sus puntos de ticket 'En Espera' (2) se ignoran, lo que hace que su carga de trabajo sea 0.
        assert data["assigned_tech_id"] == tech_a["_id"]


@pytest.mark.anyio
async def test_auto_assignment_tie_breaker_oldest(setup_db):
    """
    Verify tie-breaker sorting selects the technician with the oldest 'ultima_asignacion_at' date.
    - Tech A and Tech B both have 0 tickets assigned (Workload = 0).
    - Tech B was assigned a ticket recently. Tech A has the epoch date (1970-01-01).
    - Verify Auto-assign selects Tech A.
    """
    db = Database.get_db()
    tech_a = await TechnicianDAO.create(name="Técnico A", rut="12.345.678-5", email="tech.a@techhelp.cl", especialidad="Hardware")
    tech_b = await TechnicianDAO.create(name="Técnico B", rut="11.111.111-1", email="tech.b@techhelp.cl", especialidad="Hardware")

    # Configurar manualmente ultima_asignacion_at de Tech B en una fecha reciente, manteniendo Tech A en la época
    recent_date = (datetime.now(timezone.utc) - timedelta(minutes=5)).replace(tzinfo=None)
    await db[TechnicianDAO.collection_name].update_one(
        {"_id": ObjectId(tech_b["_id"])},
        {"$set": {"ultima_asignacion_at": recent_date}}
    )

    # Crear nuevo ticket para autoasignar
    new_ticket = await TicketDAO.create(
        title="Nuevo Ticket",
        description="Ticket de prueba de redes inalámbricas corporativas largas y extensas.",
        customer_id="12345678-5",
        categoria="Hardware",
        prioridad="Alta"
    )

    # Activar asignación automática
    admin_token = create_access_token({"sub": "admin@techhelp.cl", "role": "Administrador"})
    headers = {"Authorization": f"Bearer {admin_token}"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(f"/api/v1/tickets/{new_ticket['_id']}/auto-assign", json={"version": new_ticket["__v"]}, headers=headers)
        assert res.status_code == 200
        data = res.json()
        
        # Se debe elegir el Tech A porque su ultima_asignacion_at (1970-01-01) es más antigua que la del Tech B (fecha_reciente)
        assert data["assigned_tech_id"] == tech_a["_id"]
        
        # Verifique que ultima_asignacion_at de Tech A esté actualizado a una marca de tiempo reciente (dentro de los últimos segundos)
        updated_tech_a = await TechnicianDAO.get_by_id(tech_a["_id"])
        last_assign = updated_tech_a["ultima_asignacion_at"]
        
        # Asegúrese de que se haya actualizado a una fecha y hora reciente
        assert last_assign.year == datetime.now(timezone.utc).year
        recent_date_naive = recent_date.replace(tzinfo=None) if recent_date.tzinfo is not None else recent_date
        last_assign_naive = last_assign.replace(tzinfo=None) if last_assign.tzinfo is not None else last_assign
        assert last_assign_naive > recent_date_naive

@pytest.mark.anyio
async def test_update_initial_password_flow(setup_db):
    """
    Test PUT /api/v1/technicians/update-initial-password:
    - 8 character minimum validation.
    - Default password exclusion.
    - OCC check.
    """
    from backend.security.auth import hash_password, create_access_token
    
    # 1. Crear técnico que requiera cambio de contraseña
    tech = await TechnicianDAO.create(
        name="Carlos Silva",
        rut="12.345.678-5",
        email="carlos.silva@techhelp.cl",
        especialidad="Hardware",
        password_hash=hash_password("tech123"),
        requires_password_change=True
    )
    
    # 2. Generar encabezado de autenticación
    token = create_access_token(data={"sub": tech["email"], "role": "Tecnico"})
    headers = {"Authorization": f"Bearer {token}"}
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Prueba A: Contraseña demasiado corta (< 8 caracteres)
        payload_short = {"password": "short77", "version": tech["__v"]}
        res_short = await ac.put("/api/v1/technicians/update-initial-password", json=payload_short, headers=headers)
        assert res_short.status_code == 422
        
        # Prueba B: Contraseña predeterminada bloqueada
        payload_default = {"password": "tech123", "version": tech["__v"]}
        res_default = await ac.put("/api/v1/technicians/update-initial-password", json=payload_default, headers=headers)
        assert res_default.status_code == 422
        
        # Prueba C: error de concurrencia de OCC
        payload_occ = {"password": "newsecurepassword123", "version": tech["__v"] + 999}
        res_occ = await ac.put("/api/v1/technicians/update-initial-password", json=payload_occ, headers=headers)
        assert res_occ.status_code == 409
        
        # Prueba D: Éxito
        payload_ok = {"password": "newsecurepassword123", "version": tech["__v"]}
        res_ok = await ac.put("/api/v1/technicians/update-initial-password", json=payload_ok, headers=headers)
        assert res_ok.status_code == 200
        data_ok = res_ok.json()
        assert data_ok["__v"] == tech["__v"] + 1
        
        # Verificar el estado de la base de datos
        updated_tech = await TechnicianDAO.get_collection().find_one({"email": tech["email"]})
        assert updated_tech["requires_password_change"] is False