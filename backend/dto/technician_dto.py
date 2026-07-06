from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, EmailStr, field_validator
from backend.dto.organization_dto import validate_chilean_rut

# Estados de disponibilidad permitidos
AvailabilityStatusType = Literal["Disponible", "En Terreno", "Licencia"]

# Especialidades permitidas (RF-003)
SpecialtyType = Literal["Hardware", "Software", "Redes"]

class TechnicianCreateDTO(BaseModel):
    name: str = Field(..., min_length=3, max_length=100, json_schema_extra={"example": "Juan Pérez"})
    rut: str = Field(..., description="RUT del técnico (ej: 12.345.678-9)")
    email: EmailStr = Field(..., json_schema_extra={"example": "juan.perez@techhelp.cl"})
    especialidad: SpecialtyType = Field(..., description="Especialidad del técnico (Hardware, Software, Redes)")

    @field_validator("rut")
    @classmethod
    def validate_rut(cls, v: str) -> str:
        return validate_chilean_rut(v)

class TechnicianStatusUpdateDTO(BaseModel):
    status: AvailabilityStatusType = Field(..., description="Nuevo estado de disponibilidad (Disponible, En Terreno, Licencia)")
    version: int = Field(..., alias="version", description="Versión actual (__v) del técnico para control de concurrencia (OCC)")

class TechnicianResponseDTO(BaseModel):
    id: str = Field(..., alias="_id")
    tech_id: int = Field(..., description="Identificador secuencial numérico autoincremental (RF-003)")
    name: str
    rut: str
    email: str
    status: str
    especialidad: str
    customer_id: str = Field(..., description="Shard key para la escalabilidad (RUT del técnico)")
    ultima_asignacion_at: datetime = Field(..., description="Timestamp de la última asignación de ticket para desempate")
    created_at: datetime
    v: int = Field(..., alias="__v")
    temp_password: Optional[str] = Field(None, description="Contraseña temporal en texto plano generada para el técnico (solo se devuelve al crear)")

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        json_schema_extra = {
            "example": {
                "_id": "60d5ec49f1a2c529a8a7c2f9",
                "tech_id": 1,
                "name": "Juan Pérez",
                "rut": "12345678-5",
                "email": "juan.perez@techhelp.cl",
                "status": "Disponible",
                "especialidad": "Software",
                "customer_id": "12345678-5",
                "ultima_asignacion_at": "1970-01-01T00:00:00Z",
                "__v": 0,
                "created_at": "2026-07-04T03:57:00Z"
            }
        }

class UpdateInitialPasswordDTO(BaseModel):
    password: str = Field(..., min_length=8, description="Nueva contraseña del técnico, mínimo 8 caracteres")
    version: int = Field(..., description="Versión actual para OCC")

    @field_validator("password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        defaults = ["tech123", "client123", "admin123", "password123"]
        if v.lower() in defaults:
            raise ValueError("La contraseña no puede ser una de las claves por defecto del sistema.")
        return v