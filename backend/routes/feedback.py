import logging
from fastapi import APIRouter, status
from backend.dto.feedback_dto import FeedbackCreateDTO
from backend.dao.feedback_dao import FeedbackDAO

logger = logging.getLogger("techhelp.routes.feedback")

router = APIRouter(
    prefix="/feedback",
    tags=["Feedback"]
)

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Registrar Evaluación de Satisfacción del Cliente (RF-023)",
    description="Permite a un cliente calificar el servicio utilizando el token seguro recibido por correo."
)
async def submit_feedback(payload: FeedbackCreateDTO):
    feedback = await FeedbackDAO.submit_feedback(
        token=payload.token,
        valoracion=payload.valoracion,
        comentarios=payload.comentarios
    )
    logger.info(f"Feedback de cliente registrado para ticket {feedback['ticket_id']}. Valoración: {payload.valoracion}")
    return feedback

from datetime import datetime, timezone
from backend.config.database import Database
from backend.middlewares.error_handler import AppError

@router.get(
    "/validate",
    status_code=status.HTTP_200_OK,
    summary="Validar Token de Encuesta",
    description="Permite verificar si un token de encuesta es válido y activo."
)
async def validate_survey_token(token: str):
    db = Database.get_db()
    token_doc = await db["survey_tokens"].find_one({"token": token})
    if not token_doc:
        raise AppError("Token de encuesta inválido o inexistente.", status_code=404)
        
    if token_doc.get("used"):
        raise AppError("Esta encuesta ya fue respondida", status_code=400)
        
    expires_at = token_doc.get("expires_at")
    if expires_at:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires_at:
            raise AppError("El token de esta encuesta ha expirado (límite de 48 horas).", status_code=400)
            
    return {"valid": True, "ticket_id": token_doc["ticket_id"]}