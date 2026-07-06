import logging
from fastapi import APIRouter, status, Path, Depends
from backend.security.auth import RoleChecker
from backend.dao.user_dao import UserDAO

logger = logging.getLogger("techhelp.routes.gdpr")

router = APIRouter(
    prefix="/users/client",
    tags=["GDPR"]
)

@router.delete(
    "/{user_id}/anonymize",
    status_code=status.HTTP_200_OK,
    summary="Anonimizar Usuario Cliente (RNF-SEG-GDPR-002)",
    description="Implementa el Derecho al Olvido anonimizando de forma irreversible el nombre y correo de un cliente, "
                "preservando el documento del usuario para evitar romper la integridad de reportería de tickets.",
    dependencies=[Depends(RoleChecker(["Administrador"]))]
)
async def anonymize_user(
    user_id: str = Path(..., description="ID del usuario en MongoDB")
):
    anon_user = await UserDAO.anonymize(user_id)
    logger.info(f"Usuario {user_id} anonimizado irreversiblemente con éxito para cumplir RNF-SEG-GDPR-002.")
    return {"message": "Usuario anonimizado exitosamente.", "user": anon_user}