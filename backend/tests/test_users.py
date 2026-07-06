import os
import pytest
from httpx import AsyncClient, ASGITransport
from bson import ObjectId

# Forzar la prueba del URI de la base de datos antes de las importaciones
os.environ["MONGO_URI"] = "mongodb://localhost:27017/techhelp_test_db"

from backend.main import app
from backend.config.database import Database
from backend.dao.organization_dao import OrganizationDAO
from backend.dao.user_dao import UserDAO
from backend.security.auth import create_access_token

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.fixture
async def setup_db(anyio_backend):
    """Initializes connection to test database, registers indexing, and cleans up before and after the test."""
    db = Database.get_db()
    await OrganizationDAO.create_indexes()
    await UserDAO.create_indexes()
    await db[OrganizationDAO.collection_name].delete_many({})
    await db[UserDAO.collection_name].delete_many({})
    
    # Completar previamente una organización de prueba
    org = await OrganizationDAO.create(
        name="Test Org for Users",
        rut="12345678-5",
        email="org@testusers.cl"
    )
    
    yield org
    await db[OrganizationDAO.collection_name].delete_many({})
    await db[UserDAO.collection_name].delete_many({})
    Database.close_db()

@pytest.mark.anyio
async def test_create_user_client_success(setup_db):
    """Test successful client creation under an existing organization."""
    org = setup_db
    admin_token = create_access_token({"sub": "admin@techhelp.cl", "role": "Administrador"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    payload = {
        "name": "Carlos Gomez",
        "email": "carlos.gomez@testusers.cl",
        "organization_id": str(org["_id"])
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/api/v1/users/client", json=payload, headers=headers)
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Carlos Gomez"
        assert data["email"] == "carlos.gomez@testusers.cl"
        assert data["organization_id"] == str(org["_id"])
        assert data["role"] == "Cliente"
        assert data["status"] == "Activo"
        
        # Verificar el encabezado personalizado para la latencia de respuesta
        assert "X-Response-Time-Ms" in response.headers
        latency = float(response.headers["X-Response-Time-Ms"])
        assert latency < 500.0

@pytest.mark.anyio
async def test_create_user_client_duplicate_email(setup_db):
    """Test registering a client user with an already registered email."""
    org = setup_db
    admin_token = create_access_token({"sub": "admin@techhelp.cl", "role": "Administrador"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    payload = {
        "name": "Carlos Gomez",
        "email": "carlos.gomez@testusers.cl",
        "organization_id": str(org["_id"])
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # La primera creación tiene éxito.
        res1 = await ac.post("/api/v1/users/client", json=payload, headers=headers)
        assert res1.status_code == 201

        # La segunda creación con un correo electrónico idéntico falla (conflicto 409)
        res2 = await ac.post("/api/v1/users/client", json=payload, headers=headers)
        assert res2.status_code == 409
        assert "ya se encuentra registrado" in res2.json()["error"]

@pytest.mark.anyio
async def test_create_user_client_organization_not_found(setup_db):
    """Test client user creation referencing a non-existent organization ID."""
    admin_token = create_access_token({"sub": "admin@techhelp.cl", "role": "Administrador"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    payload = {
        "name": "Carlos Gomez",
        "email": "carlos.gomez@testusers.cl",
        "organization_id": str(ObjectId())  # ID de objeto aleatorio
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/api/v1/users/client", json=payload, headers=headers)
        assert response.status_code == 404
        assert "organización asociada especificada no existe" in response.json()["error"]

@pytest.mark.anyio
async def test_create_user_client_unauthorized(setup_db):
    """Test that non-admin roles are restricted from accessing client creation."""
    org = setup_db
    client_token = create_access_token({"sub": "client@techhelp.cl", "role": "Cliente"})
    headers = {"Authorization": f"Bearer {client_token}"}

    payload = {
        "name": "Carlos Gomez",
        "email": "carlos.gomez@testusers.cl",
        "organization_id": str(org["_id"])
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/api/v1/users/client", json=payload, headers=headers)
        assert response.status_code == 403
        assert "acceso denegado" in response.json()["detail"].lower()