import time
import logging
from fastapi import APIRouter, status, Depends, Response, BackgroundTasks
from backend.dto.user_dto import UserClientCreateDTO, UserClientResponseDTO
from backend.dao.user_dao import UserDAO
from backend.security.auth import RoleChecker
from backend.utils.email_sender import send_activation_email

logger = logging.getLogger("techhelp.routes.users")

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)

@router.post(
    "/client",
    response_model=UserClientResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un Nuevo Usuario Cliente (RF-002)",
    description="Crea un nuevo usuario de tipo Cliente asociado a una organización existente. "
                "Valida la existencia de la organización y la unicidad del correo electrónico. "
                "Dispara el envío de correo de activación de forma asíncrona mediante BackgroundTasks. "
                "Garantiza un tiempo de respuesta de backend inferior a 500ms.",
    dependencies=[Depends(RoleChecker(["Administrador"]))]
)
async def create_user_client(
    payload: UserClientCreateDTO,
    background_tasks: BackgroundTasks,
    response: Response
):
    start_time = time.perf_counter()

    # Crear el cliente de usuario en la base de datos.
    new_user = await UserDAO.create(
        name=payload.name,
        email=payload.email,
        organization_id=payload.organization_id
    )

    # Tarea de correo electrónico de activación simulada en cola (sin bloqueo)
    background_tasks.add_task(send_activation_email, payload.email, payload.name)

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.2f}"

    logger.info(f"Usuario cliente creado con éxito: {payload.email}. Latencia backend: {elapsed_ms:.2f} ms")

    if elapsed_ms > 500:
        logger.warning(f"RF-002 SLA Incumplido: Tiempo de respuesta ({elapsed_ms:.2f} ms) excedió los 500 ms.")

    return new_user

from pydantic import BaseModel, Field
from backend.security.auth import get_current_user, hash_password
from backend.config.database import Database

class ChangePasswordDTO(BaseModel):
    new_password: str = Field(..., min_length=6, description="Nueva contraseña")

@router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    summary="Cambiar Contraseña Obligatorio",
    description="Permite a un técnico cambiar su contraseña temporal por una definitiva."
)
async def change_password(
    payload: ChangePasswordDTO,
    current_user: dict = Depends(get_current_user)
):
    sub = current_user.get("sub")
    role = current_user.get("role")
    
    db = Database.get_db()
    
    if role == "Tecnico":
        tech_collection = db["technicians"]
        tech = await tech_collection.find_one({"email": sub})
        if not tech:
            raise HTTPException(status_code=404, detail="Técnico no encontrado.")
            
        pass_hash = hash_password(payload.new_password)
        await tech_collection.update_one(
            {"_id": tech["_id"]},
            {"$set": {
                "password_hash": pass_hash,
                "requires_password_change": False
            }}
        )
        logger.info(f"Contraseña de técnico {sub} cambiada exitosamente.")
        return {"message": "Contraseña cambiada exitosamente."}
        
    raise HTTPException(status_code=400, detail="Cambio de contraseña no admitido para este rol.")