from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

class UserClientCreateDTO(BaseModel):
    name: str = Field(..., min_length=3, max_length=100, json_schema_extra={"example": "Juan Pérez"})
    email: EmailStr = Field(..., json_schema_extra={"example": "juan.perez@miempresa.cl"})
    organization_id: str = Field(..., description="ID hexadecimal de la organización asociada en MongoDB o su RUT (customer_id)", json_schema_extra={"example": "12345678-5"})

class UserClientResponseDTO(BaseModel):
    id: str = Field(..., alias="_id", description="Identificador único en MongoDB")
    name: str
    email: str
    organization_id: str
    role: str = "Cliente"
    status: str = "Activo"
    created_at: datetime

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }