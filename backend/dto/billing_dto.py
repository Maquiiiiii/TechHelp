from pydantic import BaseModel, Field
from typing import Optional

class TransactionCreateDTO(BaseModel):
    organization_id: str = Field(..., description="ID o RUT de la organización cliente que realiza el pago")
    amount: float = Field(..., gt=0, description="Monto total a facturar (debe ser mayor a 0)")

class TransactionResponseDTO(BaseModel):
    token: str = Field(..., description="Token de transacción simulado de Webpay Plus")
    redirect_url: Optional[str] = Field(None, description="URL de redirección simulada de la pasarela")
    amount: float = Field(..., description="Monto facturado")
    organization_id: str = Field(..., description="Organización asociada")
    status: str = Field(..., description="Estado de la transacción (Creado, Pagado, Rechazado)")