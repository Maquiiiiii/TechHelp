from datetime import datetime, timezone
from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from backend.config.database import Database
from backend.middlewares.error_handler import DuplicateResourceError, ConcurrencyError, AppError

class TechnicianDAO:
    collection_name = "technicians"

    @classmethod
    def get_collection(cls):
        """Async database collection accessor."""
        db = Database.get_db()
        return db[cls.collection_name]

    @classmethod
    async def get_next_sequence(cls, db, sequence_name: str) -> int:
        """Atomically increment and return the next sequence value for the counter (RF-003)."""
        result = await db["counters"].find_one_and_update(
            {"_id": sequence_name},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER
        )
        return result["seq"]

    @classmethod
    async def create_indexes(cls):
        """Create unique indexes on RUT and Email to enforce business constraints."""
        collection = cls.get_collection()
        # Limpie documentos corruptos sin rutina ni correo electrónico para evitar fallas de índice de claves duplicadas al inicio.
        await collection.delete_many({
            "$or": [
                {"rut": None},
                {"email": None},
                {"rut": {"$exists": False}},
                {"email": {"$exists": False}}
            ]
        })
        await collection.create_index("rut", unique=True)
        await collection.create_index("email", unique=True)
        await collection.create_index("customer_id")

    @classmethod
    async def create(cls, name: str, rut: str, email: str, especialidad: str, password_hash: str = None, requires_password_change: bool = False) -> dict:
        """
        Create a new technician record in MongoDB.
        Status is initialized to 'Disponible', OCC __v is set to 0, tech_id is autoincremented,
        and ultima_asignacion_at is initialized to Unix Epoch to prioritize new techs during tie-breaks.
        """
        db = Database.get_db()
        collection = cls.get_collection()

        # Recuperar atómicamente el siguiente ID secuencial (RF-003)
        tech_id = await cls.get_next_sequence(db, "technician_id")

        document = {
            "tech_id": tech_id,
            "name": name,
            "rut": rut,
            "email": email,
            "especialidad": especialidad,
            "status": "Disponible",
            "customer_id": rut,
            "ultima_asignacion_at": datetime.fromtimestamp(0, tz=timezone.utc),  # Establecer en Época (la más antigua posible)
            "__v": 0,
            "created_at": datetime.now(timezone.utc)
        }
        
        if password_hash is not None:
            document["password_hash"] = password_hash
            document["requires_password_change"] = requires_password_change

        try:
            result = await collection.insert_one(document)
            document["_id"] = str(result.inserted_id)
            return document
        except DuplicateKeyError as e:
            err_msg = str(e)
            if "rut" in err_msg:
                raise DuplicateResourceError(f"El RUT '{rut}' ya pertenece a otro técnico.")
            elif "email" in err_msg:
                raise DuplicateResourceError(f"El correo electrónico '{email}' ya se encuentra registrado por otro técnico.")
            raise DuplicateResourceError("El RUT o el Email del técnico ya están registrados.")

    @classmethod
    async def get_by_id(cls, tech_id: str) -> dict:
        """Retrieve technician by string ID."""
        collection = cls.get_collection()
        try:
            obj_id = ObjectId(tech_id)
        except Exception:
            raise AppError("Formato de ID de técnico inválido.", status_code=400)
            
        doc = await collection.find_one({"_id": obj_id})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    @classmethod
    async def get_all(cls, especialidad: str = None) -> list:
        """Fetch all technicians from the database, with optional specialty filtering."""
        collection = cls.get_collection()
        query = {}
        if especialidad:
            query["especialidad"] = especialidad
        cursor = collection.find(query)
        docs = await cursor.to_list(length=1000)
        for doc in docs:
            doc["_id"] = str(doc["_id"])
        return docs

    @classmethod
    async def update_status(cls, tech_id: str, current_version: int, new_status: str) -> dict:
        """
        Update technician availability status (RF-004) checking OCC concurrency locks.
        """
        collection = cls.get_collection()
        try:
            obj_id = ObjectId(tech_id)
        except Exception:
            raise AppError("Formato de ID de técnico inválido.", status_code=400)

        # Haga coincidir tanto el ID como la versión esperada para la seguridad de OCC
        query = {
            "_id": obj_id,
            "__v": current_version
        }

        update_doc = {
            "$set": {"status": new_status},
            "$inc": {"__v": 1}
        }

        result = await collection.find_one_and_update(
            query,
            update_doc,
            return_document=ReturnDocument.AFTER
        )

        if result is None:
            # Compruebe si el documento existe (si existe, se trata de un conflicto OCC)
            existing = await collection.find_one({"_id": obj_id})
            if not existing:
                raise AppError("El técnico no existe.", status_code=404)
            raise ConcurrencyError("Control de concurrencia: el perfil del técnico fue modificado por otro proceso simultáneamente.")

        result["_id"] = str(result["_id"])
        return result

    @classmethod
    async def delete(cls, tech_id: str, version: int) -> bool:
        """
        Delete a technician record from the database with OCC check and workload verification.
        Blocks deletion if the technician has active tickets in 'Asignado' or 'En Proceso'.
        """
        collection = cls.get_collection()
        try:
            obj_id = ObjectId(tech_id)
        except Exception:
            raise AppError("Formato de ID de técnico inválido.", status_code=400)

        tech = await collection.find_one({"_id": obj_id})
        if not tech:
            raise AppError("El técnico no existe.", status_code=404)

        if tech.get("__v", 0) != version:
            raise AppError("Conflicto de concurrencia al eliminar al técnico (OCC).", status_code=409)

        db = Database.get_db()
        # Verificar carga de trabajo: no debe tener tickets activos
        active_tickets = await db["tickets"].find_one({
            "assigned_tech_id": str(obj_id),
            "status": {"$in": ["Asignado", "En Proceso"]}
        })
        if active_tickets:
            raise AppError("No se puede eliminar al técnico porque tiene tickets activos ('Asignado' o 'En Proceso') asignados.", status_code=400)

        # Eliminar el técnico
        res = await collection.delete_one({"_id": obj_id, "__v": version})
        if res.deleted_count == 0:
            raise AppError("Conflicto de concurrencia al eliminar al técnico.", status_code=409)
        return True

    @classmethod
    async def update_initial_password(cls, email: str, current_version: int, new_password_hash: str) -> dict:
        """
        Updates technician password and sets requires_password_change to False with OCC verification.
        """
        collection = cls.get_collection()
        
        query = {
            "email": email,
            "__v": current_version
        }
        
        update_doc = {
            "$set": {
                "password_hash": new_password_hash,
                "requires_password_change": False
            },
            "$inc": {"__v": 1}
        }
        
        result = await collection.find_one_and_update(
            query,
            update_doc,
            return_document=ReturnDocument.AFTER
        )
        
        if result is None:
            existing = await collection.find_one({"email": email})
            if not existing:
                raise AppError("El técnico no existe.", status_code=404)
            raise ConcurrencyError("Control de concurrencia: el perfil del técnico fue modificado por otro proceso simultáneamente.")
            
        result["_id"] = str(result["_id"])
        return result
