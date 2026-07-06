import logging
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, status, Depends, Query, HTTPException
from backend.security.auth import RoleChecker
from backend.dto.analytics_dto import ChurnRiskCustomerResponse, CapacityProjectionResponse, CapacityProjectionItem, CapacityMonthItem
from backend.dao.analytics_dao import AnalyticsDAO

logger = logging.getLogger("techhelp.routes.analytics")

router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"]
)

def generate_last_n_months(n: int) -> List[str]:
    """
    Generates a chronological list of the last N year-month strings (YYYY-MM).
    """
    months = []
    now = datetime.now(timezone.utc)
    for i in range(n - 1, -1, -1):
        year = now.year
        month = now.month - i
        while month <= 0:
            month += 12
            year -= 1
        months.append(f"{year}-{month:02d}")
    return months

def check_sustained_growth(counts: List[int]) -> bool:
    """
    RF-026 trend calculator helper:
    Checks if there is a sustained growth of > 20% in demand consecutive month-to-month.
    Requires at least 2 data points.
    """
    if len(counts) < 2:
        return False
        
    for i in range(len(counts) - 1):
        prev = counts[i]
        curr = counts[i+1]
        if prev == 0:
            if curr > 0:
                growth = 1.0  # 100% de crecimiento
            else:
                growth = 0.0
        else:
            growth = (curr - prev) / prev
            
        if growth <= 0.20:
            return False
            
    return True

@router.get(
    "/churn-risk",
    response_model=List[ChurnRiskCustomerResponse],
    status_code=status.HTTP_200_OK,
    summary="Panel de Alerta Temprana de Churn (RF-025)",
    description="Detecta organizaciones cliente en riesgo de fuga según tasa de incidentes vencidos de SLA (>15%) "
                "y valoración de encuestas baja (<2.5 estrellas) en los últimos 14 días.",
    dependencies=[Depends(RoleChecker(["Administrador"]))]
)
async def get_churn_risk_report():
    report = await AnalyticsDAO.get_churn_risk_report()
    return report

@router.get(
    "/capacity-projection",
    response_model=CapacityProjectionResponse,
    status_code=status.HTTP_200_OK,
    summary="Proyección de Capacidad Técnica Operativa (RF-026)",
    description="Calcula la proyección de demanda mensual por especialidades técnicas en base a un histórico. "
                "Si la demanda crece consistentemente más de un 20% mensual, inyecta una alerta de contratación recomendada.",
    dependencies=[Depends(RoleChecker(["Administrador"]))]
)
async def get_capacity_projections(
    rango_meses: int = Query(default=3, ge=3, description="Rango de meses de historial a analizar (mínimo 3)")
):
    db_results = await AnalyticsDAO.get_capacity_projections(rango_meses)
    
    # Generación de línea de tiempo cronológica
    generated_months = generate_last_n_months(rango_meses)
    
    # Mapeo de estructura para llenar el vacío cronológico de meses con 0
    categories = ["Hardware", "Software", "Redes"]
    category_data = {cat: {ym: 0 for ym in generated_months} for cat in categories}
    
    for row in db_results:
        cat = row.get("categoria")
        ym = row.get("year_month")
        if cat in category_data and ym in category_data[cat]:
            category_data[cat][ym] = row["count"]
            
    projections = []
    for cat in categories:
        history_items = [
            CapacityMonthItem(year_month=ym, count=category_data[cat][ym])
            for ym in generated_months
        ]
        
        # Verificacion de tendencias
        counts = [category_data[cat][ym] for ym in generated_months]
        alerta = None
        if check_sustained_growth(counts):
            alerta = "Se recomienda la contratación inmediata de personal de soporte técnico"
            
        projections.append(CapacityProjectionItem(
            categoria=cat,
            history=history_items,
            alerta=alerta
        ))
        
    return CapacityProjectionResponse(projections=projections)