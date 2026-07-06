import re
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


def clean_rut(rut: str) -> str:
    """Helper to remove periods, hyphens, and spaces, and convert to uppercase."""
    return re.sub(r"[.\-\s]", "", rut).upper()

def validate_chilean_rut(rut: str) -> str:
    """Validate Chilean RUT format and verification digit using the Modulo 11 algorithm."""
    cleaned = clean_rut(rut)
    if not re.match(r"^\d{7,8}[0-9K]$", cleaned):
        raise ValueError("RUT inválido: Formato incorrecto. Debe contener entre 7 y 8 dígitos seguidos de un número o 'K'.")
    
    body = cleaned[:-1]
    dv = cleaned[-1]
    
    # Cálculo del módulo 11
    total_sum = 0
    multiplier = 2
    for digit in reversed(body):
        total_sum += int(digit) * multiplier
        multiplier = multiplier + 1 if multiplier < 7 else 2
        
    rem = total_sum % 11
    expected_dv_num = 11 - rem
    if expected_dv_num == 11:
        expected_dv = "0"
    elif expected_dv_num == 10:
        expected_dv = "K"
    else:
        expected_dv = str(expected_dv_num)
        
    if dv != expected_dv:
        raise ValueError(f"RUT inválido: El dígito verificador '{dv}' no coincide con el esperado '{expected_dv}'.")
    
    # Formato normalizado de devolución: XXXXXXXX-X
    return f"{body}-{dv}"

class OrganizationCreateDTO(BaseModel):
    name: str = Field(..., min_length=3, max_length=100, json_schema_extra={"example": "TechHelp Solutions"})
    rut: str = Field(..., json_schema_extra={"example": "12.345.678-9"})
    email: EmailStr = Field(..., json_schema_extra={"example": "contacto@techhelp.cl"})
    tier_contractual: Literal["Bronce", "Plata", "Oro"] = Field(default="Bronce", json_schema_extra={"example": "Oro"})
    industria: str = Field(..., description="Industria de la organización", json_schema_extra={"example": "Tecnología"})

    @field_validator("rut")
    @classmethod
    def validate_rut(cls, v: str) -> str:
        return validate_chilean_rut(v)

class OrganizationResponseDTO(BaseModel):
    id: str = Field(..., alias="_id", description="Identificador único en MongoDB")
    name: str
    rut: str
    email: str
    tier_contractual: str
    customer_id: str = Field(..., description="Shard key para escalabilidad horizontal (mapeado al RUT)")
    v: int = Field(..., alias="__v", description="Versión de control de concurrrencia optimista (OCC)")
    created_at: datetime
    industria: Optional[str] = Field(None, description="Industria de la organización")
    tickets_count: int = 0
    activo: bool = Field(default=True, description="Indica si la organización está activa")

    class Config:
        populate_by_name = True

        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        json_schema_extra = {
            "example": {
                "_id": "60d5ec49f1a2c529a8a7c2f1",
                "name": "TechHelp Solutions",
                "rut": "12345678-5",
                "email": "contacto@techhelp.cl",
                "tier_contractual": "Oro",
                "industria": "Tecnología",
                "tickets_count": 5,
                "__v": 0,
                "created_at": "2026-07-04T03:30:00Z"
            }
        }