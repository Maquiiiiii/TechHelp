import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/techhelp_db")

class Database:
    client: AsyncIOMotorClient = None
    db = None

    @classmethod
    def get_db(cls):
        if cls.db is None:
            cls.client = AsyncIOMotorClient(MONGO_URI)
            # Recuperar el nombre de la base de datos del URI, por defecto techhelp_db
            db_name = MONGO_URI.split("/")[-1].split("?")[0] or "techhelp_db"
            cls.db = cls.client[db_name]
        return cls.db

    @classmethod
    def close_db(cls):
        if cls.client is not None:
            cls.client.close()
            cls.client = None
            cls.db = None