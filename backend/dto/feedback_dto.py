from pydantic import BaseModel, Field, field_validator
from typing import Optional

class FeedbackCreateDTO(BaseModel):
    token: str = Field(..., description="Token criptográfico único asociado a la encuesta")
    valoracion: int = Field(..., ge=1, le=5, description="Valoración entera estricta de satisfacción del 1 al 5")
    comentarios: Optional[str] = Field(None, description="Comentarios adicionales opcionales del cliente")

    @field_validator("valoracion")
    @classmethod
    def validate_valoracion(cls, v: int) -> int:
        if not isinstance(v, int):
            raise ValueError("La valoración de estrellas debe ser estrictamente un número entero.")
        if v < 1 or v > 5:
            raise ValueError("La valoración debe estar en el rango de 1 a 5 estrellas.")
        return v