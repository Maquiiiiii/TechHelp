from datetime import datetime, timezone
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from typing import Literal, Optional
from backend.config.database import Database
from backend.middlewares.error_handler import DuplicateResourceError, ConcurrencyError, AppError

class OrganizationDAO:
    collection_name = "organizations"

    @classmethod
    def get_collection(cls):
        """Helper to get the MongoDB collection instance asynchronously."""
        db = Database.get_db()
        return db[cls.collection_name]

    @classmethod
    async def create_indexes(cls):
        """Create unique indexes on RUT and Email to enforce business rules at the database level."""
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
        # Establezca el valor predeterminado activo = Verdadero para cualquier organización existente que no lo tenga
        await collection.update_many(
            {"activo": {"$exists": False}},
            {"$set": {"activo": True}}
        )
        await collection.create_index("rut", unique=True)
        await collection.create_index("email", unique=True)
        await collection.create_index("customer_id")

    @classmethod
    async def create(cls, name: str, rut: str, email: str, tier_contractual: Literal["Bronce", "Plata", "Oro"] = "Bronce", industria: str = None, **kwargs) -> dict:
        """
        Create a new organization record in MongoDB.
        Initializes the OCC version (__v) to 0 and registers customer_id (RUT) for horizontal sharding.
        """
        if "nivel_soporte" in kwargs:
            tier_contractual = kwargs["nivel_soporte"]

        collection = cls.get_collection()
        
        document = {
            "name": name,
            "rut": rut,
            "email": email,
            "tier_contractual": tier_contractual,
            "customer_id": rut,  # Clave de fragmento basada en RUT (RNF-ESC-SHARDING)
            "industria": industria,
            "activo": True,
            "__v": 0,            # Versión inicial de OCC (corrección RNF-ESC-003)
            "created_at": datetime.now(timezone.utc)
        }

        
        try:
            result = await collection.insert_one(document)
            document["_id"] = str(result.inserted_id)
            return document
        except DuplicateKeyError as e:
            # Cree un mensaje fácil de usar basado en detalles de excepción de clave duplicada
            err_msg = str(e)
            if "rut" in err_msg:
                raise DuplicateResourceError(f"El RUT '{rut}' ya se encuentra registrado por otra organización.")
            elif "email" in err_msg:
                raise DuplicateResourceError(f"El correo electrónico '{email}' ya se encuentra registrado.")
            raise DuplicateResourceError("El RUT o el Email ya están registrados.")

    @classmethod
    async def get_by_id(cls, org_id: str) -> dict:
        """Retrieve organization by string ID."""
        collection = cls.get_collection()
        try:
            obj_id = ObjectId(org_id)
        except Exception:
            raise AppError("Formato de ID inválido.", status_code=400)
            
        doc = await collection.find_one({"_id": obj_id})
        if doc:
            doc["_id"] = str(doc["_id"]) # Convierta ObjectId en cadena para serialización JSON
            if "activo" not in doc:
                doc["activo"] = True
        return doc

    @classmethod
    async def get_all(cls, search: str = None) -> list:
        """Fetch all organizations from the database with optional search and ticket counts."""
        collection = cls.get_collection()
        query = {}
        if search:
            query = {
                "$or": [
                    {"name": {"$regex": search, "$options": "i"}},
                    {"rut": {"$regex": search, "$options": "i"}},
                    {"email": {"$regex": search, "$options": "i"}},
                    {"email_corporativo": {"$regex": search, "$options": "i"}},
                    {"razon_social": {"$regex": search, "$options": "i"}},
                    {"industria": {"$regex": search, "$options": "i"}}
                ]
            }

        pipeline = [
            {"$match": query},
            {
                "$lookup": {
                    "from": "tickets",
                    "localField": "rut",
                    "foreignField": "customer_id",
                    "as": "tickets_asociados"
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "name": 1,
                    "rut": 1,
                    "email": 1,
                    "email_corporativo": 1,
                    "razon_social": 1,
                    "tier_contractual": 1,
                    "customer_id": 1,
                    "industria": 1,
                    "activo": {"$ifNull": ["$activo", True]},
                    "__v": 1,
                    "created_at": 1,
                    "tickets_count": {"$size": "$tickets_asociados"}
                }
            }
        ]

        cursor = collection.aggregate(pipeline)
        docs = await cursor.to_list(length=1000)
        for doc in docs:
            doc["_id"] = str(doc["_id"]) # Convierta ObjectId en cadena para serialización JSON
        return docs

    @classmethod
    async def update(cls, org_id: str, current_version: int, update_data: dict) -> dict:
        """
        Update an organization record applying Optimistic Concurrency Control (OCC).
        Matching __v with current_version guarantees that no updates have happened in the meantime.
        """
        collection = cls.get_collection()
        try:
            obj_id = ObjectId(org_id)
        except Exception:
            raise AppError("Formato de ID inválido.", status_code=400)

        # Haga coincidir tanto el identificador del documento como el código de versión (verificación OCC)
        query = {
            "_id": obj_id,
            "__v": current_version
        }
        
        # Incrementar __v y aplicar variables establecidas
        update_doc = {
            "$set": update_data,
            "$inc": {"__v": 1}
        }
        
        # Si actualizamos el RUT, también debemos actualizar la clave del fragmento customer_id
        if "rut" in update_data:
            update_doc["$set"]["customer_id"] = update_data["rut"]

        from pymongo import ReturnDocument
        try:
            result = await collection.find_one_and_update(
                query,
                update_doc,
                return_document=ReturnDocument.AFTER
            )
        except DuplicateKeyError as e:
            err_msg = str(e)
            if "rut" in err_msg:
                raise DuplicateResourceError("El nuevo RUT ya está registrado por otra organización.")
            elif "email" in err_msg:
                raise DuplicateResourceError("El nuevo correo electrónico ya está registrado.")
            raise DuplicateResourceError("Conflicto de unicidad en RUT o Email.")

        if result is None:
            # Determinar si la actualización falló porque el documento no existe o debido a un conflicto de versiones.
            existing = await collection.find_one({"_id": obj_id})
            if not existing:
                raise AppError("La organización no existe.", status_code=404)
            # Si existe, pero la actualización no coincide con la versión: colisión OCC
            raise ConcurrencyError()

        if update_data.get("activo") is False:
            # Actualización en cascada: cerrar tickets activos
            db = Database.get_db()
            org_rut = result["rut"]
            justification = "Ticket cerrado automáticamente por desactivación de la organización cliente"
            now_time = datetime.now(timezone.utc)
            
            tickets_cursor = db["tickets"].find({
                "customer_id": org_rut,
                "status": {"$nin": ["Cerrado", "Rechazado"]}
            })
            active_tickets = await tickets_cursor.to_list(length=1000)
            
            for ticket in active_tickets:
                set_fields = {
                    "status": "Cerrado",
                    "comentario_solucion": justification,
                    "resuelto_at": now_time
                }
                inc_fields = {
                    "__v": 1
                }
                
                if ticket.get("status") == "En Espera":
                    en_espera_start = ticket.get("en_espera_at")
                    if en_espera_start:
                        if en_espera_start.tzinfo is None:
                            en_espera_start = en_espera_start.replace(tzinfo=timezone.utc)
                        paused_delta = now_time - en_espera_start
                        paused_minutes = paused_delta.total_seconds() / 60
                    else:
                        paused_minutes = 0.0
                    inc_fields["minutos_en_espera_acumulados"] = paused_minutes
                    set_fields["en_espera_at"] = None

                await db["tickets"].update_one(
                    {"_id": ticket["_id"]},
                    {
                        "$set": set_fields,
                        "$inc": inc_fields,
                        "$push": {
                            "comentarios": {
                                "id": str(ObjectId()),
                                "texto": justification,
                                "autor_nombre": "Sistema",
                                "autor_email": "soporte@techhelp.cl",
                                "autor_rol": "Sistema",
                                "es_interno": False,
                                "created_at": now_time
                            }
                        }
                    }
                )

        result["_id"] = str(result["_id"])
        return result

    @classmethod
    async def delete(cls, org_id: str, version: int) -> bool:
        """
        Logically deactivates the organization and closes all its active tickets.
        Matches original signature to keep existing test paths valid but implements logical deletion.
        """
        collection = cls.get_collection()
        try:
            obj_id = ObjectId(org_id)
        except Exception:
            raise AppError("Formato de ID inválido.", status_code=400)

        # verificación OCC
        query = {
            "_id": obj_id,
            "__v": version
        }
        
        update_doc = {
            "$set": {"activo": False},
            "$inc": {"__v": 1}
        }
        
        from pymongo import ReturnDocument
        result = await collection.find_one_and_update(
            query,
            update_doc,
            return_document=ReturnDocument.AFTER
        )
        
        if result is None:
            existing = await collection.find_one({"_id": obj_id})
            if not existing:
                raise AppError("La organización no existe.", status_code=404)
            raise ConcurrencyError()

        # Actualización en cascada: cerrar tickets activos
        db = Database.get_db()
        org_rut = result["rut"]
        justification = "Ticket cerrado automáticamente por desactivación de la organización cliente"
        now_time = datetime.now(timezone.utc)
        
        tickets_cursor = db["tickets"].find({
            "customer_id": org_rut,
            "status": {"$nin": ["Cerrado", "Rechazado"]}
        })
        active_tickets = await tickets_cursor.to_list(length=1000)
        
        for ticket in active_tickets:
            set_fields = {
                "status": "Cerrado",
                "comentario_solucion": justification,
                "resuelto_at": now_time
            }
            inc_fields = {
                "__v": 1
            }
            
            if ticket.get("status") == "En Espera":
                en_espera_start = ticket.get("en_espera_at")
                if en_espera_start:
                    if en_espera_start.tzinfo is None:
                        en_espera_start = en_espera_start.replace(tzinfo=timezone.utc)
                    paused_delta = now_time - en_espera_start
                    paused_minutes = paused_delta.total_seconds() / 60
                else:
                    paused_minutes = 0.0
                inc_fields["minutos_en_espera_acumulados"] = paused_minutes
                set_fields["en_espera_at"] = None

            await db["tickets"].update_one(
                {"_id": ticket["_id"]},
                {
                    "$set": set_fields,
                    "$inc": inc_fields,
                    "$push": {
                        "comentarios": {
                            "id": str(ObjectId()),
                            "texto": justification,
                            "autor_nombre": "Sistema",
                            "autor_email": "soporte@techhelp.cl",
                            "autor_rol": "Sistema",
                            "es_interno": False,
                            "created_at": now_time
                        }
                    }
                }
            )
            
        return True

    @classmethod
    async def toggle_status(cls, org_id: str, version: int) -> dict:
        """
        Alterna el estado de activación de la organización.
        Si pasa a False (desactivado), cierra en cascada sus tickets activos.
        """
        collection = cls.get_collection()
        try:
            obj_id = ObjectId(org_id)
        except Exception:
            raise AppError("Formato de ID inválido.", status_code=400)

        org = await collection.find_one({"_id": obj_id})
        if not org:
            raise AppError("La organización no existe.", status_code=404)

        current_active = org.get("activo", True)
        next_active = not current_active

        query = {
            "_id": obj_id,
            "__v": version
        }
        
        update_doc = {
            "$set": {"activo": next_active},
            "$inc": {"__v": 1}
        }
        
        from pymongo import ReturnDocument
        result = await collection.find_one_and_update(
            query,
            update_doc,
            return_document=ReturnDocument.AFTER
        )
        
        if result is None:
            raise ConcurrencyError()

        if not next_active:
            # Actualización en cascada: cerrar tickets activos
            db = Database.get_db()
            org_rut = result["rut"]
            justification = "Ticket cerrado automáticamente por desactivación de la organización cliente"
            now_time = datetime.now(timezone.utc)
            
            tickets_cursor = db["tickets"].find({
                "customer_id": org_rut,
                "status": {"$nin": ["Cerrado", "Rechazado"]}
            })
            active_tickets = await tickets_cursor.to_list(length=1000)
            
            for ticket in active_tickets:
                set_fields = {
                    "status": "Cerrado",
                    "comentario_solucion": justification,
                    "resuelto_at": now_time
                }
                inc_fields = {
                    "__v": 1
                }
                
                if ticket.get("status") == "En Espera":
                    en_espera_start = ticket.get("en_espera_at")
                    if en_espera_start:
                        if en_espera_start.tzinfo is None:
                            en_espera_start = en_espera_start.replace(tzinfo=timezone.utc)
                        paused_delta = now_time - en_espera_start
                        paused_minutes = paused_delta.total_seconds() / 60
                    else:
                        paused_minutes = 0.0
                    inc_fields["minutos_en_espera_acumulados"] = paused_minutes
                    set_fields["en_espera_at"] = None

                await db["tickets"].update_one(
                    {"_id": ticket["_id"]},
                    {
                        "$set": set_fields,
                        "$inc": inc_fields,
                        "$push": {
                            "comentarios": {
                                "id": str(ObjectId()),
                                "texto": justification,
                                "autor_nombre": "Sistema",
                                "autor_email": "soporte@techhelp.cl",
                                "autor_rol": "Sistema",
                                "es_interno": False,
                                "created_at": now_time
                            }
                        }
                    }
                )
        
        result["_id"] = str(result["_id"])
        return result