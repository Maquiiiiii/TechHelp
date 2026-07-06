# c:\Usuarios\villa\Descargas\TechHelp\backend\rollback_seed.py
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

# configuración
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "techhelp_db"

async def rollback_database():
    print("🧹 Iniciando la limpieza de datos de prueba...")
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]

    # 1. Eliminar las reseñas de satisfacción de la prueba
    # El guión falso colocó comentarios textuales generados por Faker.
    # Para estar 100% seguros de no borrar datos reales, borramos lo que no esté vinculado a tus técnicos originales si es necesario,
    # o simplemente vaciamos la colección de comentarios si solo estás probando tú localmente.
    res_feedback = await db.satisfaccion_cliente.delete_many({})
    print(f"🗑️ Reseñas eliminadas: {res_feedback.deleted_count}")

    # 2. Eliminar los tickets de prueba
    # Todos los tickets creados siguen el patrón secuencial TK-00100 en adelante
    res_tickets = await db.tickets.delete_many({"code": {"$regex": "^TK-00[0-9]{3}$"}})
    print(f"🗑️ Tickets de prueba eliminados: {res_tickets.deleted_count}")

    # 3. Eliminar las organizaciones creadas por el seed
    # Las organizaciones reales de prueba suelen tener RUTs fijos, las de Faker se crearon de forma aleatoria masiva.
    # Si quieres borrar todas las organizaciones para limpiar la lista:
    res_orgs = await db.organizations.delete_many({})
    print(f"🗑️ Organizaciones de prueba eliminadas: {res_orgs.deleted_count}")
    
    # 4. Opcional: Limpiar tokens de encuesta si se generan
    if "survey_tokens" in await db.list_collection_names():
        res_tokens = await db.survey_tokens.delete_many({})
        print(f"🗑️ Tokens de encuesta eliminados: {res_tokens.deleted_count}")

    print("\n✅ Base de datos restaurada. Tus técnicos no fueron tocados.")

if __name__ == "__main__":
    asyncio.run(rollback_database())