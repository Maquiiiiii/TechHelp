from pydantic import BaseModel, Field
from typing import Optional, List

class ChurnRiskCustomerResponse(BaseModel):
    customer_id: str = Field(..., description="RUT de la organización cliente")
    organization_name: Optional[str] = Field(None, description="Nombre descriptivo de la organización")
    organization_email: Optional[str] = Field(None, description="Email de contacto de la organización")
    total_tickets: int = Field(..., description="Volumen total de incidentes creados en los últimos 14 días")
    tasa_violacion_sla: float = Field(..., description="Proporción (0.0 a 1.0) de violaciones efectivas de SLA")
    satisfaccion_promedio: Optional[float] = Field(None, description="Promedio de encuestas recibidas en los últimos 14 días")
    riesgo_inminente_cancelacion: bool = Field(..., description="Bandera indicando riesgo crítico de fuga (SLA > 15% y Satisfacción < 2.5)")

class CapacityMonthItem(BaseModel):
    year_month: str = Field(..., description="Año y mes agrupado (YYYY-MM)")
    count: int = Field(..., description="Cantidad de incidentes cerrados en ese mes")

class CapacityProjectionItem(BaseModel):
    categoria: str = Field(..., description="Especialidad técnica (Hardware, Software, Redes)")
    history: List[CapacityMonthItem] = Field(..., description="Historial cronológico de demanda mensual")
    alerta: Optional[str] = Field(None, description="Mensaje de recomendación de contratación si se detecta incremento sostenido > 20%")

class CapacityProjectionResponse(BaseModel):
    projections: List[CapacityProjectionItem] = Field(..., description="Lista de proyecciones por especialidad técnica")