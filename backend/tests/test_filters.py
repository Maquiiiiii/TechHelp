import os
import pytest
from httpx import AsyncClient, ASGITransport

# Forzar la prueba del URI de la base de datos antes de las importaciones
os.environ["MONGO_URI"] = "mongodb://localhost:27017/techhelp_test_db"

from backend.main import app
from backend.config.database import Database
from backend.dao.organization_dao import OrganizationDAO
from backend.dao.ticket_dao import TicketDAO
from backend.dao.technician_dao import TechnicianDAO
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
    await db["counters"].delete_many({})
    
    # Complete previamente dos organizaciones de prueba
    await OrganizationDAO.create(
        name="TechHelp Client Org A",
        rut="12345678-5",
        email="client.a@techhelp.cl",
        industria="Tecnología"
    )
    await OrganizationDAO.create(
        name="Another Company B",
        rut="87654321-4",
        email="client.b@techhelp.cl",
        industria="Retail"
    )

    # Precompletar dos técnicos
    await TechnicianDAO.create(
        name="Tech Software",
        rut="11111111-1",
        email="tech.soft@techhelp.cl",
        especialidad="Software"
    )
    await TechnicianDAO.create(
        name="Tech Hardware",
        rut="22222222-2",
        email="tech.hard@techhelp.cl",
        especialidad="Hardware"
    )
    
    yield
    await db[OrganizationDAO.collection_name].delete_many({})
    await db[TicketDAO.collection_name].delete_many({})
    await db[TechnicianDAO.collection_name].delete_many({})
    await db["counters"].delete_many({})
    Database.close_db()

@pytest.mark.anyio
async def test_tickets_filtering_and_security(setup_db):
    """Test ticket search, filters, and security boundaries (multi-tenancy)."""
    # 1. Entradas Cree para la organización A.
    t1 = await TicketDAO.create(
        title="Software error in database connection",
        description="El sistema de base de datos del servidor central arroja timeout constante.",
        customer_id="12345678-5",
        categoria="Software",
        prioridad="Alta"
    )
    t2 = await TicketDAO.create(
        title="Hardware problem with keyboard A",
        description="El teclado del servidor del rack principal no funciona ni enciende.",
        customer_id="12345678-5",
        categoria="Hardware",
        prioridad="Baja"
    )

    # Crear ticket para la organización B
    t3 = await TicketDAO.create(
        title="Database server connectivity B",
        description="Conexión intermitente en las bases de datos de reportes mensuales.",
        customer_id="87654321-4",
        categoria="Software",
        prioridad="Crítica"
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # A) Búsqueda del Cliente de prueba A: SÓLO debería ver tickets de la Organización A
        token_a = create_access_token({"sub": "client.a@techhelp.cl", "role": "Cliente", "organization_rut": "12345678-5"})
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # Buscar "base de datos"
        res = await ac.get("/api/v1/tickets?search=database", headers=headers_a)
        assert res.status_code == 200
        tickets_list = res.json()
        assert len(tickets_list) == 1
        assert tickets_list[0]["code"] == t1["code"]  # ¡Solo debe devolver t1 de la organización A, no t3 de la organización B!

        # Intente buscar la búsqueda exacta del código de la organización B; no debería devolver NADA para el cliente A
        res_exact = await ac.get(f"/api/v1/tickets?search={t3['code']}", headers=headers_a)
        assert res_exact.status_code == 200
        assert len(res_exact.json()) == 0

        # Filtrar por prioridad
        res_prio = await ac.get("/api/v1/tickets?prioridad=Alta", headers=headers_a)
        assert res_prio.status_code == 200
        assert len(res_prio.json()) == 1
        assert res_prio.json()[0]["code"] == t1["code"]

        # B) Búsqueda de técnico/administrador de pruebas: puede ver todos los tickets y la descripción de la búsqueda
        token_tech = create_access_token({"sub": "tech.soft@techhelp.cl", "role": "Tecnico"})
        headers_tech = {"Authorization": f"Bearer {token_tech}"}

        # Buscar base de datos
        res_tech = await ac.get("/api/v1/tickets?search=database", headers=headers_tech)
        assert res_tech.status_code == 200
        assert len(res_tech.json()) == 2  # Debería ver t1 y t3

        # Descripción de la búsqueda
        res_desc = await ac.get("/api/v1/tickets?search=teclado", headers=headers_tech)
        assert res_desc.status_code == 200
        assert len(res_desc.json()) == 1
        assert res_desc.json()[0]["code"] == t2["code"]

@pytest.mark.anyio
async def test_organizations_smart_search_and_tickets_count(setup_db):
    """Test smart search and ticket count aggregation in organization list."""
    # Crear entradas
    await TicketDAO.create(
        title="Issue one with software",
        description="El sistema de base de datos del servidor central arroja timeout constante.",
        customer_id="12345678-5",
        categoria="Software",
        prioridad="Alta"
    )
    await TicketDAO.create(
        title="Issue two with software",
        description="El sistema de base de datos del servidor central arroja timeout constante.",
        customer_id="12345678-5",
        categoria="Software",
        prioridad="Baja"
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        token_admin = create_access_token({"sub": "admin@techhelp.cl", "role": "Administrador"})
        headers_admin = {"Authorization": f"Bearer {token_admin}"}

        # Listar organizaciones: comprobar recuentos
        res = await ac.get("/api/v1/organizations", headers=headers_admin)
        assert res.status_code == 200
        orgs = res.json()
        assert len(orgs) == 2
        
        # La organización A debería tener 2 entradas, la organización B debería tener 0
        org_a = next(o for o in orgs if o["rut"] == "12345678-5")
        org_b = next(o for o in orgs if o["rut"] == "87654321-4")
        assert org_a["tickets_count"] == 2
        assert org_b["tickets_count"] == 0

        # Búsqueda inteligente: coincidencia por industria "Venta al por menor"
        res_search_ind = await ac.get("/api/v1/organizations?search=Retail", headers=headers_admin)
        assert res_search_ind.status_code == 200
        res_orgs = res_search_ind.json()
        assert len(res_orgs) == 1
        assert res_orgs[0]["rut"] == "87654321-4"

        # Búsqueda inteligente: coincidencia por rutina parcial
        res_search_rut = await ac.get("/api/v1/organizations?search=12345", headers=headers_admin)
        assert len(res_search_rut.json()) == 1
        assert res_search_rut.json()[0]["rut"] == "12345678-5"

@pytest.mark.anyio
async def test_technicians_specialty_filter(setup_db):
    """Test specialty filter on technician list."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        token_admin = create_access_token({"sub": "admin@techhelp.cl", "role": "Administrador"})
        headers_admin = {"Authorization": f"Bearer {token_admin}"}

        # Especialidad en software de filtrado
        res_soft = await ac.get("/api/v1/technicians?especialidad=Software", headers=headers_admin)
        assert res_soft.status_code == 200
        techs_soft = res_soft.json()
        assert len(techs_soft) == 1
        assert techs_soft[0]["name"] == "Tech Software"

        # Especialidad en hardware de filtrado
        res_hard = await ac.get("/api/v1/technicians?especialidad=Hardware", headers=headers_admin)
        assert res_hard.status_code == 200
        techs_hard = res_hard.json()
        assert len(techs_hard) == 1
        assert techs_hard[0]["name"] == "Tech Hardware"

@pytest.mark.anyio
async def test_ticket_comments_identity_and_finalization_blocking(setup_db):
    """Test that comments capture user name, email, role, and block additions on finalized tickets."""
    # 1. Crea un billete
    ticket = await TicketDAO.create(
        title="Test comments blocking",
        description="This ticket is used to verify comments identity and terminal blocking rules.",
        customer_id="12345678-5",
        categoria="Software",
        prioridad="Media"
    )
    ticket_id = ticket["_id"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        token_tech = create_access_token({"sub": "tech.soft@techhelp.cl", "role": "Tecnico", "name": "Tech Software"})
        headers_tech = {"Authorization": f"Bearer {token_tech}"}

        # A) Agregar comentario para abrir ticket -> verificar metadatos de identidad en respuesta
        payload = {"texto": "Este es un comentario de prueba", "es_interno": False}
        res_add = await ac.post(f"/api/v1/tickets/{ticket_id}/comments", json=payload, headers=headers_tech)
        assert res_add.status_code == 201
        updated = res_add.json()
        
        # Verifique que el comentario se haya enviado con el nombre, el correo electrónico y la función del autor adecuada
        comments = updated["comentarios"]
        assert len(comments) == 1
        comment = comments[0]
        assert comment["autor_nombre"] == "Tech Software"
        assert comment["autor_email"] == "tech.soft@techhelp.cl"
        assert comment["autor_rol"] == "Tecnico"
        assert comment["texto"] == "Este es un comentario de prueba"

        # B) Boleto de transición al Cerrado
        from bson import ObjectId
        db = Database.get_db()
        await db[TicketDAO.collection_name].update_one(
            {"_id": ObjectId(ticket_id)},
            {"$set": {"status": "Cerrado"}}
        )

        # C) Intente comentar sobre el ticket cerrado -> verificar el bloqueo de 400 solicitudes incorrectas
        res_fail = await ac.post(f"/api/v1/tickets/{ticket_id}/comments", json=payload, headers=headers_tech)
        assert res_fail.status_code == 400
        assert "No se pueden añadir comentarios a un ticket finalizado" in res_fail.json()["detail"]