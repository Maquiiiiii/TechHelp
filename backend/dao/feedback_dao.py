from datetime import datetime, timezone
from backend.config.database import Database
from backend.middlewares.error_handler import AppError

class FeedbackDAO:
    @classmethod
    async def submit_feedback(cls, token: str, valoracion: int, comentarios: str = None) -> dict:
        """
        RF-023: Submits client feedback validated by a unique cryptographic token.
        Inserts details into a new collection 'satisfaccion_cliente' without mutating the ticket document.
        Marks token as used.
        """
        db = Database.get_db()
        token_doc = await db["survey_tokens"].find_one({"token": token})
        
        if not token_doc:
            raise AppError("Token de encuesta inválido o inexistente.", status_code=404)
            
        if token_doc.get("used"):
            raise AppError("El token de esta encuesta ya ha sido utilizado.", status_code=400)
            
        expires_at = token_doc.get("expires_at")
        if expires_at:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires_at:
                raise AppError("El token de esta encuesta ha expirado (límite de 48 horas).", status_code=400)

        # Crear documento de comentarios
        feedback_doc = {
            "ticket_id": token_doc["ticket_id"],
            "customer_email": token_doc["customer_email"],
            "valoracion": valoracion,
            "comentarios": comentarios,
            "tech_id": token_doc.get("tech_id"),
            "tech_name": token_doc.get("tech_name"),
            "created_at": datetime.now(timezone.utc)
        }
        
        # guardar comentarios
        result = await db["satisfaccion_cliente"].insert_one(feedback_doc)
        feedback_doc["_id"] = str(result.inserted_id)
        
        # Marcar token como usado
        await db["survey_tokens"].update_one(
            {"_id": token_doc["_id"]},
            {"$set": {"used": True}}
        )
        
        return feedback_doc