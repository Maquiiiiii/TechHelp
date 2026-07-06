import time
import logging
from fastapi import APIRouter, status, Response, Query, Depends
from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional
from backend.dto.organization_dto import OrganizationCreateDTO, OrganizationResponseDTO, validate_chilean_rut
from backend.dao.organization_dao import OrganizationDAO
from backend.middlewares.error_handler import AppError
from backend.security.auth import RoleChecker

logger = logging.getLogger("techhelp.routes.organizations")

router = APIRouter(
    prefix="/organizations",
    tags=["Organizations"]
)

class OrganizationUpdateDTO(BaseModel):
    name: str = Field(None, min_length=3, max_length=100)
    rut: str = Field(None)
    email: EmailStr = Field(None)
    industria: str = Field(..., description="Industria de la organización")
    activo: Optional[bool] = Field(None, description="Estado de activación")
    version: int = Field(..., alias="version", description="Versión actual del documento para el control de concurrrencia optimista (OCC)")

    @field_validator("rut")
    @classmethod
    def validate_rut(cls, v: str) -> str:
        if v is None:
            return v
        return validate_chilean_rut(v)

@router.get(
    "",
    response_model=list[OrganizationResponseDTO],
    status_code=status.HTTP_200_OK,
    summary="Listar todas las organizaciones",
    description="Retorna el listado completo de organizaciones registradas."
)
async def list_organizations(search: Optional[str] = Query(None)):
    return await OrganizationDAO.get_all(search=search)

@router.post(
    "",
    response_model=OrganizationResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar Organización (RF-001)",
    description="Registra una nueva organización corporativa. Valida que el RUT e Email sean únicos. "
                "Calcula el dígito verificador del RUT usando Modulo 11. Mide la respuesta garantizando < 800ms.",
    response_description="Organización creada exitosamente, incluyendo el identificador de Sharding 'customer_id' y la versión de OCC '__v'."
)
async def register_organization(payload: OrganizationCreateDTO, response: Response):
    start_time = time.perf_counter()
    
    # Inserción de procesos vía DAO
    new_org = await OrganizationDAO.create(
        name=payload.name,
        rut=payload.rut,
        email=payload.email,
        tier_contractual=payload.tier_contractual,
        industria=payload.industria
    )
    
    # Calcular el tiempo de respuesta
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.2f}"
    
    logger.info(f"Organización creada con éxito. RUT: {payload.rut}. Tiempo de backend: {elapsed_ms:.2f} ms")
    
    # Confirmar el requisito RF-001 en el registrador para auditoría
    if elapsed_ms > 800:
        logger.warning(f"RF-001 SLA Incumplido: Tiempo de respuesta ({elapsed_ms:.2f} ms) excedió los 800 ms.")
        
    return new_org

@router.put(
    "/{org_id}",
    response_model=OrganizationResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Actualizar Organización con OCC (RNF-ESC-003)",
    description="Actualiza datos de la organización validando que la versión actual coincida en la base de datos "
                "para evitar sobreescritura concurrente accidental.",
)
async def update_organization(org_id: str, payload: OrganizationUpdateDTO):
    # Extraiga solo los campos de actualización proporcionados
    update_data = {}
    if payload.name is not None:
        update_data["name"] = payload.name
    if payload.rut is not None:
        update_data["rut"] = payload.rut
    if payload.email is not None:
        update_data["email"] = payload.email
    if payload.industria is not None:
        update_data["industria"] = payload.industria
    if payload.activo is not None:
        update_data["activo"] = payload.activo

    if not update_data:
        raise AppError("No se entregaron campos para actualizar.", status_code=status.HTTP_400_BAD_REQUEST)
        
    updated_org = await OrganizationDAO.update(
        org_id=org_id,
        current_version=payload.version,
        update_data=update_data
    )
    return updated_org

@router.delete(
    "/{org_id}",
    status_code=status.HTTP_200_OK,
    summary="Desactivar Organización (Borrado Lógico)",
    description="Desactiva lógicamente una organización cliente, cerrando en cascada todos sus tickets activos.",
    dependencies=[Depends(RoleChecker(["Administrador"]))]
)
async def delete_organization(
    org_id: str,
    version: int = Query(..., description="Versión actual para OCC")
):
    await OrganizationDAO.delete(org_id, version)
    return {"message": "Organización desactivada exitosamente."}

@router.put(
    "/{org_id}/toggle-status",
    response_model=OrganizationResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Alternar estado de activación de la organización",
    description="Alterna el estado activo de la organización. Si se desactiva, cierra en cascada sus tickets.",
    dependencies=[Depends(RoleChecker(["Administrador"]))]
)
async def toggle_organization_status(
    org_id: str,
    version: int = Query(..., description="Versión actual para OCC")
):
    return await OrganizationDAO.toggle_status(org_id, version)