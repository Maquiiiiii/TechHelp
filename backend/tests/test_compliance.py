import os
import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone
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
    await db["billing_transactions"].delete_many({})
    await db["audit_logs"].delete_many({})
    
    # Completar previamente una organización de prueba
    org = await OrganizationDAO.create(
        name="Compliance Client Org",
        rut="12345678-5",
        email="client@compliance.cl"
    )
    
    yield org
    await db[OrganizationDAO.collection_name].delete_many({})
    await db[UserDAO.collection_name].delete_many({})
    await db["billing_transactions"].delete_many({})
    await db["audit_logs"].delete_many({})
    Database.close_db()

@pytest.mark.anyio
async def test_gdpr_client_anonymization(setup_db):
    """Test Right to be Forgotten (GDPR) client anonymization (RNF-SEG-GDPR-002)."""
    org = setup_db
    db = Database.get_db()

    # 1. Cree un usuario cliente
    user = await UserDAO.create(
        name="Juan Diaz",
        email="juan.diaz@compliance.cl",
        organization_id=str(org["_id"])
    )
    user_id = user["_id"]

    # 2. Anonimización de solicitud de función no administrativa (debe fallar con 403)
    tech_token = create_access_token({"sub": "tecnico@techhelp.cl", "role": "Tecnico"})
    headers_tech = {"Authorization": f"Bearer {tech_token}"}
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response_tech = await ac.delete(f"/api/v1/users/client/{user_id}/anonymize", headers=headers_tech)
        assert response_tech.status_code == 403

        # 3. Solicitud de anonimización del rol de administrador (debe tener éxito con 200)
        admin_token = create_access_token({"sub": "admin@techhelp.cl", "role": "Administrador"})
        headers_admin = {"Authorization": f"Bearer {admin_token}"}
        
        response_admin = await ac.delete(f"/api/v1/users/client/{user_id}/anonymize", headers=headers_admin)
        assert response_admin.status_code == 200
        
        # Verifique que el documento aún exista en la base de datos pero esté anónimo
        db_user = await db["users"].find_one({"_id": ObjectId(user_id)})
        assert db_user is not None
        assert db_user["name"] == "Usuario Eliminado"
        assert db_user["email"].startswith("anon_")
        assert db_user["email"].endswith("@techhelp.local")
        assert db_user["status"] == "Inactivo"

@pytest.mark.anyio
async def test_webpay_billing_transactions(setup_db):
    """Test initiating and confirming Webpay Plus transactions (RNF-COM-007)."""
    org = setup_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Iniciar transacción
        payload_create = {
            "organization_id": org["rut"],
            "amount": 15000.0
        }
        response_init = await ac.post("/api/v1/billing/transactions", json=payload_create)
        assert response_init.status_code == 201
        data_init = response_init.json()
        assert data_init["status"] == "Creado"
        assert "token" in data_init
        assert "redirect_url" in data_init
        assert data_init["amount"] == 15000.0
        
        token = data_init["token"]

        # 2. Confirmar transacción
        response_confirm = await ac.put(f"/api/v1/billing/transactions/{token}")
        assert response_confirm.status_code == 200
        data_confirm = response_confirm.json()
        assert data_confirm["status"] == "Pagado"

        # 3. Verificación de confirmación duplicada (debe fallar con 400)
        response_dup = await ac.put(f"/api/v1/billing/transactions/{token}")
        assert response_dup.status_code == 400
        assert "ya ha sido pagada" in response_dup.json()["error"]


@pytest.mark.anyio
async def test_audit_log_validation_success_and_failure():
    """Verify that AuditLogDTO validation rules are enforced strictly (RF-014 / RNF-SEG-004)."""
    from pydantic import ValidationError
    from backend.dto.ticket_dto import AuditLogDTO

    # feliz camino
    valid_data = {
        "id_ticket": "TK-12345",
        "id_operador": "op123@techhelp.cl",
        "accion": "Cambio de Estado",
        "valor_anterior": "Abierto",
        "nuevo_valor": "Asignado",
        "timestamp": datetime.now(timezone.utc),
        "ip_origen": "192.168.1.50"
    }
    dto = AuditLogDTO(**valid_data)
    assert dto.id_ticket == "TK-12345"

    # Ruta fallida (código de expresión regular no válido)
    invalid_data = valid_data.copy()
    invalid_data["id_ticket"] = "TK-123"  # longitud/formato no válido
    with pytest.raises(ValidationError):
        AuditLogDTO(**invalid_data)

    invalid_data["id_ticket"] = "12345"  # prefijo faltante
    with pytest.raises(ValidationError):
        AuditLogDTO(**invalid_data)


@pytest.mark.anyio
async def test_registrar_evento_forense_persistence(setup_db):
    """Verify that registrar_evento_forense saves the document to audit_logs (RF-014)."""
    from backend.dao.log_dao import LogDAO
    from backend.dto.ticket_dto import AuditLogDTO
    db = Database.get_db()

    valid_log = AuditLogDTO(
        id_ticket="TK-99999",
        id_operador="tecnico@techhelp.cl",
        accion="Autoasignación",
        valor_anterior="Abierto",
        nuevo_valor="Asignado",
        timestamp=datetime.now(timezone.utc),
        ip_origen="127.0.0.1"
    )

    inserted_id = await LogDAO.registrar_evento_forense(valid_log)
    assert isinstance(inserted_id, str)

    saved = await db["audit_logs"].find_one({"id_ticket": "TK-99999"})
    assert saved is not None
    assert saved["id_operador"] == "tecnico@techhelp.cl"
    assert saved["accion"] == "Autoasignación"


@pytest.mark.anyio
async def test_registrar_evento_forense_operation_failure(setup_db):
    """Verify that registrar_evento_forense mutates OperationFailure to HTTPException(403) (RNF-SEG-004)."""
    from unittest.mock import patch, AsyncMock, MagicMock
    from pymongo.errors import OperationFailure
    from fastapi import HTTPException
    from backend.dao.log_dao import LogDAO
    from backend.dto.ticket_dto import AuditLogDTO

    valid_log = AuditLogDTO(
        id_ticket="TK-88888",
        id_operador="tecnico@techhelp.cl",
        accion="Actualización",
        valor_anterior="Asignado",
        nuevo_valor="En Proceso",
        timestamp=datetime.now(timezone.utc),
        ip_origen="127.0.0.1"
    )

    mock_collection = MagicMock()
    mock_collection.insert_one = AsyncMock(side_effect=OperationFailure("Mocked write privilege error (Read-Only violation)"))

    with patch.object(LogDAO, "_get_collection", return_value=mock_collection):
        with pytest.raises(HTTPException) as exc_info:
            await LogDAO.registrar_evento_forense(valid_log)
        assert exc_info.value.status_code == 403
        assert "Violación de la política de inmutabilidad" in exc_info.value.detail