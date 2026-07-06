import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

MONGO_URI = (
    os.getenv("MONGO_URI") or 
    os.getenv("MONGO_URL") or 
    os.getenv("MONGODB_URL") or 
    "mongodb://localhost:27017/techhelp_db"
)

class Database:
    client: AsyncIOMotorClient = None
    db = None

    @classmethod
    def get_db(cls):
        if cls.db is None:
            cls.client = AsyncIOMotorClient(MONGO_URI)
            # Recuperar el nombre de la base de datos del URI, por defecto techhelp_db
            from urllib.parse import urlparse
            parsed = urlparse(MONGO_URI)
            db_name = parsed.path.strip("/")
            if db_name:
                db_name = db_name.split("?")[0]
            if not db_name:
                db_name = "techhelp_db"
            cls.db = cls.client[db_name]
        return cls.db

    @classmethod
    def close_db(cls):
        if cls.client is not None:
            cls.client.close()
            cls.client = None
            cls.db = None