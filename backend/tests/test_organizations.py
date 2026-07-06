import os
import pytest
from httpx import AsyncClient, ASGITransport
from pydantic import ValidationError

# Forzar la prueba del URI de la base de datos antes de las importaciones para evitar contaminar la base de datos de producción.
os.environ["MONGO_URI"] = "mongodb://localhost:27017/techhelp_test_db"

from backend.main import app
from backend.config.database import Database
from backend.dto.organization_dto import OrganizationCreateDTO
from backend.dao.organization_dao import OrganizationDAO

@pytest.fixture
def anyio_backend():
    """Specify backend for anyio tests."""
    return "asyncio"

@pytest.fixture
async def setup_db(anyio_backend):
    """Initializes connection to test database, runs indexing, and cleans up before and after the test."""
    db = Database.get_db()
    await OrganizationDAO.create_indexes()
    await db[OrganizationDAO.collection_name].delete_many({})
    yield
    await db[OrganizationDAO.collection_name].delete_many({})
    Database.close_db()  # Borrar la instancia de la base de datos para que la próxima prueba vincule a un cliente al nuevo bucle de eventos

# ==========================================
# 1. PRUEBAS DE VALIDACIÓN DTO (Sincrónicas)
# ==========================================

def test_dto_valid_rut_and_email():
    """Verify that valid RUTs and email formats are successfully parsed by the DTO."""
    dto = OrganizationCreateDTO(
        name="Test Org Ltd",
        rut="12.345.678-5",
        email="info@testorg.com",
        industria="Tecnología"
    )
    assert dto.name == "Test Org Ltd"
    assert dto.rut == "12345678-5"  # Debe normalizarse (limpiarse y dividirse con guiones)
    assert dto.email == "info@testorg.com"

def test_dto_invalid_rut_digit_verifier():
    """Verify that a RUT with incorrect verification digit fails validation."""
    with pytest.raises(ValidationError) as excinfo:
        OrganizationCreateDTO(
            name="Bad Rut Org",
            rut="12.345.678-9",
            email="info@badorg.cl"
        )
    assert "dígito verificador" in str(excinfo.value)

def test_dto_invalid_rut_format():
    """Verify that a RUT with wrong layout/length fails validation."""
    with pytest.raises(ValidationError) as excinfo:
        OrganizationCreateDTO(
            name="Bad Format Org",
            rut="123-K",
            email="info@badorg.cl"
        )
    assert "RUT inválido" in str(excinfo.value)

def test_dto_invalid_email_format():
    """Verify that Pydantic rejects emails with invalid syntax."""
    with pytest.raises(ValidationError):
        OrganizationCreateDTO(
            name="Bad Email Org",
            rut="12.345.678-5",
            email="not-an-email"
        )


# ==========================================
# 2. PRUEBAS DE REGISTRO DE ENDPOINT (Asíncrono)
# ==========================================

@pytest.mark.anyio
async def test_api_create_organization_success(setup_db):
    """Test successful organization registration through the HTTP API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "name": "Acme Corporation",
            "rut": "12.345.678-5",
            "email": "contact@acme.com",
            "industria": "Tecnología"
        }
        response = await ac.post("/api/v1/organizations", json=payload)
        
        assert response.status_code == 201
        data = response.json()
        
        assert "_id" in data
        assert data["name"] == "Acme Corporation"
        assert data["rut"] == "12345678-5"
        assert data["email"] == "contact@acme.com"
        assert data["customer_id"] == "12345678-5"
        assert data["__v"] == 0
        
        # Verifique que el encabezado SLA de tiempo de respuesta esté presente
        assert "X-Response-Time-Ms" in response.headers
        assert float(response.headers["X-Response-Time-Ms"]) > 0

@pytest.mark.anyio
async def test_api_create_organization_duplicate_conflict(setup_db):
    """Test that creating an organization with duplicate RUT or email returns 409 Conflict."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload_1 = {
            "name": "Org Prime",
            "rut": "12.345.678-5",
            "email": "prime@domain.com",
            "industria": "Tecnología"
        }
        res1 = await ac.post("/api/v1/organizations", json=payload_1)
        assert res1.status_code == 201

        payload_2 = {
            "name": "Org Secondary",
            "rut": "12.345.678-5",
            "email": "sec@domain.com",
            "industria": "Tecnología"
        }
        res2 = await ac.post("/api/v1/organizations", json=payload_2)
        assert res2.status_code == 409
        assert "RUT" in res2.json()["error"]

        payload_3 = {
            "name": "Org Tertiary",
            "rut": "11.111.111-1",
            "email": "prime@domain.com",
            "industria": "Tecnología"
        }
        res3 = await ac.post("/api/v1/organizations", json=payload_3)
        assert res3.status_code == 409
        assert "correo" in res3.json()["error"]


# ==========================================
# 3. PRUEBAS DE CONCURRENCIA OCC (Asíncrono)
# ==========================================

@pytest.mark.anyio
async def test_occ_concurrency_update(setup_db):
    """Test that updating an organization with outdated version throws a 409 conflict."""
    org = await OrganizationDAO.create(
        name="OCC Corp",
        rut="12.345.678-5",
        email="occ@corp.cl"
    )
    org_id = org["_id"]
    version = org["__v"]
    assert version == 0
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        update_1 = {
            "name": "OCC Corp Renamed",
            "industria": "Tecnología",
            "version": version
        }
        res1 = await ac.put(f"/api/v1/organizations/{org_id}", json=update_1)
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["name"] == "OCC Corp Renamed"
        assert data1["__v"] == 1
        
        update_2 = {
            "name": "OCC Corp Overwrite",
            "industria": "Tecnología",
            "version": 0  # Versión obsoleta
        }
        res2 = await ac.put(f"/api/v1/organizations/{org_id}", json=update_2)
        assert res2.status_code == 409
        assert "concurrencia" in res2.json()["error"]