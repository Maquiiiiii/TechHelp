import logging
from typing import Optional
from fastapi import APIRouter, status, Path, Query, Depends, HTTPException
from backend.dto.technician_dto import TechnicianCreateDTO, TechnicianStatusUpdateDTO, TechnicianResponseDTO, UpdateInitialPasswordDTO
from backend.dao.technician_dao import TechnicianDAO
from backend.security.auth import RoleChecker, hash_password, get_current_user


logger = logging.getLogger("techhelp.routes.technicians")

router = APIRouter(
    prefix="/technicians",
    tags=["Technicians"]
)

@router.get(
    "",
    response_model=list[TechnicianResponseDTO],
    status_code=status.HTTP_200_OK,
    summary="Listar todos los técnicos",
    description="Retorna el listado completo de técnicos registrados."
)
async def list_technicians(especialidad: Optional[str] = Query(None)):
    return await TechnicianDAO.get_all(especialidad=especialidad)

from backend.utils.password_generator import generate_secure_password
from backend.security.auth import hash_password

@router.post(
    "",
    response_model=TechnicianResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un Nuevo Técnico (RF-003)",
    description="Registra un nuevo técnico de soporte en el sistema con especialidad (Hardware, Software, Redes). "
                "Valida la unicidad del RUT y del Email y le asigna un ID secuencial autoincremental."
)
async def register_technician(payload: TechnicianCreateDTO):
    temp_pass = generate_secure_password(10)
    pass_hash = hash_password(temp_pass)
    
    new_tech = await TechnicianDAO.create(
        name=payload.name,
        rut=payload.rut,
        email=payload.email,
        especialidad=payload.especialidad,
        password_hash=pass_hash,
        requires_password_change=True
    )
    logger.info(f"Técnico registrado exitosamente con ID {new_tech['tech_id']}. RUT: {payload.rut}")
    new_tech["temp_password"] = temp_pass
    return new_tech

from fastapi import HTTPException
from backend.security.auth import get_current_user

@router.get(
    "/me",
    response_model=TechnicianResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Obtener perfil del técnico autenticado",
    description="Retorna el perfil del técnico actualmente autenticado en base a su token."
)
async def get_current_technician_profile(
    current_user: dict = Depends(get_current_user)
):
    email = current_user.get("sub")
    tech = await TechnicianDAO.get_collection().find_one({"email": email})
    if not tech:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Perfil de técnico no encontrado."
        )
    tech["_id"] = str(tech["_id"])
    return tech

@router.put(
    "/me/status",
    response_model=TechnicianResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Actualizar disponibilidad del técnico autenticado",
    description="Permite al técnico autenticado cambiar su disponibilidad ('Disponible', 'En Terreno', 'Licencia')."
)
async def update_my_status(
    payload: TechnicianStatusUpdateDTO,
    current_user: dict = Depends(get_current_user)
):
    email = current_user.get("sub")
    tech = await TechnicianDAO.get_collection().find_one({"email": email})
    if not tech:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Perfil de técnico no encontrado."
        )
    
    updated_tech = await TechnicianDAO.update_status(
        tech_id=str(tech["_id"]),
        current_version=payload.version,
        new_status=payload.status
    )
    return updated_tech

@router.put(
    "/{tech_id}/status",
    response_model=TechnicianResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Actualizar Estado del Técnico (RF-004, RNF-ESC-003)",
    description="Actualiza la disponibilidad del técnico ('Disponible', 'En Terreno', 'Licencia'). "
                "Utiliza el control de concurrencia optimista (OCC) validando la versión (__v)."
)
async def update_technician_status(
    tech_id: str = Path(..., description="ID hexadecimal del técnico en MongoDB"),
    payload: TechnicianStatusUpdateDTO = ...
):
    updated_tech = await TechnicianDAO.update_status(
        tech_id=tech_id,
        current_version=payload.version,
        new_status=payload.status
    )
    logger.info(f"Estado de disponibilidad del técnico {tech_id} cambiado a '{payload.status}'")
    return updated_tech

@router.delete(
    "/{tech_id}",
    status_code=status.HTTP_200_OK,
    summary="Eliminar Técnico con OCC",
    description="Elimina un perfil de técnico validando control de concurrencia optimista y carga de trabajo activa.",
    dependencies=[Depends(RoleChecker(["Administrador"]))]
)
async def delete_technician(
    tech_id: str = Path(..., description="ID hexadecimal del técnico en MongoDB"),
    version: int = Query(..., description="Versión actual para OCC")
):
    await TechnicianDAO.delete(tech_id, version)
    logger.info(f"Técnico con ID {tech_id} eliminado exitosamente.")
    return {"message": "Técnico eliminado exitosamente."}

@router.put(
    "/update-initial-password",
    response_model=TechnicianResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Actualizar contraseña inicial obligatoria",
    description="Permite al técnico actualizar su contraseña por primera vez. "
                "Valida criterios de seguridad, elimina el flag requires_password_change "
                "e incrementa la versión (__v) usando OCC."
)
async def update_initial_password(
    payload: UpdateInitialPasswordDTO,
    current_user: dict = Depends(get_current_user)
):
    email = current_user.get("sub")
    role = current_user.get("role")
    
    # 1. Validar que el usuario es técnico
    if role != "Tecnico":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: este recurso solo está disponible para técnicos."
        )
        
    # 2. Hachís de contraseña
    hashed_pass = hash_password(payload.password)
    
    # 3. Actualizar base de datos con OCC
    updated_tech = await TechnicianDAO.update_initial_password(
        email=email,
        current_version=payload.version,
        new_password_hash=hashed_pass
    )
    
    logger.info(f"Contraseña inicial actualizada con éxito para el técnico {email}.")
    return updated_tech
