from datetime import datetime, timezone
from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import DuplicateKeyError
from backend.config.database import Database
from backend.dao.organization_dao import OrganizationDAO
from backend.middlewares.error_handler import AppError, DuplicateResourceError

class UserDAO:
    collection_name = "users"

    @classmethod
    def get_collection(cls):
        """Helper to get the MongoDB collection instance asynchronously."""
        db = Database.get_db()
        return db[cls.collection_name]

    @classmethod
    async def create_indexes(cls):
        """Create unique indexes on Email to enforce uniqueness at the database level."""
        collection = cls.get_collection()
        await collection.create_index("email", unique=True)

    @classmethod
    async def create(cls, name: str, email: str, organization_id: str) -> dict:
        """
        Create a new user client in MongoDB.
        Verifies organization existence and email uniqueness.
        """
        # 1. Verificar la existencia de la organización
        org_collection = OrganizationDAO.get_collection()
        org = None
        
        # Pruebe la consulta de MongoDB ObjectId
        try:
            org = await org_collection.find_one({"_id": ObjectId(organization_id)})
        except (InvalidId, TypeError):
            pass

        # Si no lo encuentra por ObjectId, intente buscar por customer_id (RUT)
        if not org:
            org = await org_collection.find_one({"customer_id": organization_id})

        if not org:
            raise AppError("La organización asociada especificada no existe.", status_code=404)

        # 2. Verifique la unicidad del correo electrónico en la colección de usuarios.
        collection = cls.get_collection()
        existing_user = await collection.find_one({"email": email})
        if existing_user:
            raise DuplicateResourceError(f"El correo electrónico '{email}' ya se encuentra registrado por otro usuario.")

        # 3. Crear documento de usuario
        document = {
            "name": name,
            "email": email,
            "organization_id": str(org["_id"]),  # Normalizar la cadena ObjectId de la organización
            "role": "Cliente",
            "status": "Activo",
            "created_at": datetime.now(timezone.utc)
        }

        try:
            result = await collection.insert_one(document)
            document["_id"] = str(result.inserted_id)
            return document
        except DuplicateKeyError:
            raise DuplicateResourceError(f"El correo electrónico '{email}' ya se encuentra registrado.")

    @classmethod
    async def anonymize(cls, user_id: str) -> dict:
        """
        RNF-SEG-GDPR-002: Irreversibly anonymizes user details to respect the Right to be Forgotten (GDPR).
        Does not physically delete the document to preserve ticket reports.
        Replaces name and email with generic/placeholder hash values.
        """
        collection = cls.get_collection()
        try:
            obj_id = ObjectId(user_id)
        except Exception:
            raise AppError("Formato de ID de usuario inválido.", status_code=400)
            
        user = await collection.find_one({"_id": obj_id})
        if not user:
            raise AppError("El usuario no existe.", status_code=404)
            
        import secrets
        random_hash = secrets.token_hex(4)
        anon_name = "Usuario Eliminado"
        anon_email = f"anon_{random_hash}@techhelp.local"
        
        result = await collection.find_one_and_update(
            {"_id": obj_id},
            {"$set": {
                "name": anon_name,
                "email": anon_email,
                "status": "Inactivo",
                "anonymized_at": datetime.now(timezone.utc)
            }},
            return_document=True
        )
        if result:
            result["_id"] = str(result["_id"])
        return result