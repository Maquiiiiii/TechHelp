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
from backend.dao.technician_dao import TechnicianDAO
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
    await TechnicianDAO.create_indexes()
    await UserDAO.create_indexes()
    
    await db[OrganizationDAO.collection_name].delete_many({})
    await db[TechnicianDAO.collection_name].delete_many({})
    await db[UserDAO.collection_name].delete_many({})
    await db["tickets"].delete_many({})
    
    # Completar previamente la organización de la prueba
    org = await OrganizationDAO.create(
        name="Delete Test Org",
        rut="12345678-5",
        email="delete.org@test.cl",
        nivel_soporte="Oro"
    )
    
    # Llenar previamente el técnico de pruebas.
    tech = await TechnicianDAO.create(
        name="Delete Tech",
        rut="9876543-2",
        email="delete.tech@test.cl",
        especialidad="Hardware"
    )
    
    yield {"org": org, "tech": tech}
    
    await db[OrganizationDAO.collection_name].delete_many({})
    await db[TechnicianDAO.collection_name].delete_many({})
    await db[UserDAO.collection_name].delete_many({})
    await db["tickets"].delete_many({})
    Database.close_db()

@pytest.mark.anyio
async def test_organization_delete_constraints(setup_db):
    """Tests organization logical deletion (deactivation) and cascading ticket closures."""
    db_data = setup_db
    org = db_data["org"]
    org_id = org["_id"]
    org_version = org["__v"]
    
    admin_token = create_access_token({"sub": "admin@techhelp.cl", "role": "Administrador"})
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        db = Database.get_db()
        
        # 1. Crear tickets activos bajo esta organización (customer_id = RUT)
        await db["tickets"].insert_one({
            "code": "TK-DEL-01",
            "status": "Abierto",
            "customer_id": org["rut"],
            "categoria": "Hardware",
            "created_at": datetime.now(timezone.utc),
            "__v": 0
        })
        await db["tickets"].insert_one({
            "code": "TK-DEL-02",
            "status": "En Espera",
            "en_espera_at": datetime.now(timezone.utc),
            "customer_id": org["rut"],
            "categoria": "Software",
            "created_at": datetime.now(timezone.utc),
            "__v": 0
        })
        # Un ticket ya cerrado (no debe cambiar/incrementar ni agregar comentarios duplicados)
        await db["tickets"].insert_one({
            "code": "TK-DEL-03",
            "status": "Cerrado",
            "customer_id": org["rut"],
            "categoria": "Redes",
            "created_at": datetime.now(timezone.utc),
            "__v": 0
        })
        
        # 2. Llamar al punto final de eliminación lógica (desactivación)
        res_success = await ac.delete(f"/api/v1/organizations/{org_id}?version={org_version}", headers=headers)
        assert res_success.status_code == 200
        assert "desactivada exitosamente" in res_success.json()["message"]
        
        # 3. Verifique el estado activo de la organización en la base de datos.
        updated_org = await db["organizations"].find_one({"_id": ObjectId(org_id)})
        assert updated_org["activo"] is False
        
        # 4. Verifique que los tickets activos se cierren automáticamente en cascada
        ticket1 = await db["tickets"].find_one({"code": "TK-DEL-01"})
        assert ticket1["status"] == "Cerrado"
        assert "desactivación de la organización cliente" in ticket1["comentario_solucion"]
        assert len(ticket1["comentarios"]) == 1
        assert ticket1["comentarios"][0]["autor_nombre"] == "Sistema"
        
        ticket2 = await db["tickets"].find_one({"code": "TK-DEL-02"})
        assert ticket2["status"] == "Cerrado"
        assert ticket2["en_espera_at"] is None
        assert ticket2["minutos_en_espera_acumulados"] >= 0
        
        ticket3 = await db["tickets"].find_one({"code": "TK-DEL-03"})
        assert ticket3["status"] == "Cerrado"
        assert "comentarios" not in ticket3 or len(ticket3["comentarios"]) == 0
        
        # 5. Verifique que el punto final de estado vuelva a estar activo
        res_toggle = await ac.put(f"/api/v1/organizations/{org_id}/toggle-status?version={updated_org['__v']}", headers=headers)
        assert res_toggle.status_code == 200
        assert res_toggle.json()["activo"] is True

@pytest.mark.anyio
async def test_technician_delete_constraints(setup_db):
    """Tests technician deletion happy path and workload blocks."""
    db_data = setup_db
    tech = db_data["tech"]
    tech_id = tech["_id"]
    tech_version = tech["__v"]
    
    admin_token = create_access_token({"sub": "admin@techhelp.cl", "role": "Administrador"})
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Cree un ticket en estado "Asignado" asignado a este técnico
        db = Database.get_db()
        await db["tickets"].insert_one({
            "code": "TK-TECH-01",
            "status": "Asignado",
            "customer_id": "11111111-1",
            "assigned_tech_id": tech_id,
            "assigned_tech_name": tech["name"],
            "created_at": datetime.now(timezone.utc)
        })
        
        # Intente eliminar: debería fallar con 400 debido a la carga de trabajo del ticket activo
        res_fail = await ac.delete(f"/api/v1/technicians/{tech_id}?version={tech_version}", headers=headers)
        assert res_fail.status_code == 400
        assert "tickets activos" in res_fail.json()["error"]
        
        # limpiar boletos
        await db["tickets"].delete_many({})
        
        # 2. Eliminación feliz del camino
        res_success = await ac.delete(f"/api/v1/technicians/{tech_id}?version={tech_version}", headers=headers)
        assert res_success.status_code == 200
        assert "eliminado exitosamente" in res_success.json()["message"]