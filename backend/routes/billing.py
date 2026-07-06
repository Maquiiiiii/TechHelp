import logging
from fastapi import APIRouter, status, Path
from backend.dto.billing_dto import TransactionCreateDTO, TransactionResponseDTO
from backend.utils.transbank_service import TransbankService

logger = logging.getLogger("techhelp.routes.billing")

router = APIRouter(
    prefix="/billing",
    tags=["Billing"]
)

@router.post(
    "/transactions",
    response_model=TransactionResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Iniciar Pago Webpay Plus (RNF-COM-007)",
    description="Inicia el flujo de pago con Transbank Webpay Plus, generando una URL de redirección y token de pago."
)
async def initiate_payment(payload: TransactionCreateDTO):
    tx = await TransbankService.initiate_transaction(
        organization_id=payload.organization_id,
        amount=payload.amount
    )
    logger.info(f"Transacción Webpay Plus iniciada para org {payload.organization_id} con monto {payload.amount}")
    return tx

@router.put(
    "/transactions/{token}",
    response_model=TransactionResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Confirmar Transacción de Pago (RNF-COM-007)",
    description="Valida el token de pago y confirma la facturación cambiando el estado de la transacción a 'Pagado'."
)
async def confirm_payment(
    token: str = Path(..., description="Token de transacción devuelto por la pasarela de pagos")
):
    tx = await TransbankService.confirm_transaction(token)
    logger.info(f"Transacción de pago confirmada y facturada para el token {token}")
    return tx