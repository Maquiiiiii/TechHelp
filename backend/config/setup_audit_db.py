import os
from pymongo import MongoClient
from pymongo.errors import PyMongoError

def setup_audit_database():
    """
    RNF-SEG-004: Configures an immutable, append-only 'audit_logs' collection
    by setting up a custom database role that permits only 'insert' and 'find'
    actions, blocking any 'update' or 'remove' requests.
    """
    mongo_uri = (
        os.getenv("MONGO_URI") or 
        os.getenv("MONGO_URL") or 
        os.getenv("MONGODB_URL") or 
        "mongodb://localhost:27017/techhelp_db"
    )
    print(f"Connecting to MongoDB at {mongo_uri}...")
    client = MongoClient(mongo_uri)
    try:
        db = client.get_database()
        if db is None or not db.name:
            db = client["techhelp_db"]
    except Exception:
        db = client["techhelp_db"]
    
    # 1. Crear colección si no existe
    collection_name = "audit_logs"
    if collection_name not in db.list_collection_names():
        db.create_collection(collection_name)
        print(f"Created collection '{collection_name}' successfully.")
    else:
        print(f"Collection '{collection_name}' already exists.")
        
    # 2. Registrador función de base de datos personalizados de solo agregar
    try:
        # Comprobar si el rol existe
        db.command("rolesInfo", "appendOnlyAuditLogs")
        print("Custom database role 'appendOnlyAuditLogs' already exists.")
    except PyMongoError:
        try:
            db.command(
                "createRole",
                "appendOnlyAuditLogs",
                privileges=[
                    {
                        "resource": { "db": db.name, "collection": collection_name },
                        "actions": [ "insert", "find" ]
                    }
                ],
                roles=[]
            )
            print("Successfully created custom role 'appendOnlyAuditLogs' (Append-Only model).")
        except Exception as e:
            print(f"Note: Custom role creation skipped or failed: {str(e)}.")
            print("Ensure that write privileges on 'audit_logs' are restricted strictly to insertion actions.")
            
    client.close()

if __name__ == "__main__":
    setup_audit_database()