import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, status, Depends, Query
from backend.dao.dashboard_dao import DashboardDAO
from backend.security.auth import RoleChecker
from backend.dao.log_dao import LogDAO

logger = logging.getLogger("techhelp.routes.dashboard")

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"]
)

def resolve_date_range(start_date: str = None, end_date: str = None, period: str = None):
    """
    Parses optional inputs to resolve to timezone-aware UTC datetime start and end bounds.
    """
    now = datetime.now(timezone.utc)
    
    if start_date or end_date:
        if start_date:
            try:
                s_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                s_dt = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        else:
            s_dt = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
            
        if end_date:
            try:
                e_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc)
            except ValueError:
                e_dt = now
        else:
            e_dt = now
            
        return s_dt, e_dt
        
    elif period:
        try:
            year, month = map(int, period.split("-"))
            s_dt = datetime(year, month, 1, tzinfo=timezone.utc)
            if month == 12:
                next_year = year + 1
                next_month = 1
            else:
                next_year = year
                next_month = month + 1
            e_dt = datetime(next_year, next_month, 1, tzinfo=timezone.utc) - timedelta(microseconds=1)
            return s_dt, e_dt
        except Exception:
            pass
            
    # Valor predeterminado: desde el inicio del mes calendario actual hasta ahora
    s_dt = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    e_dt = now
    return s_dt, e_dt

@router.get(
    "/metrics",
    status_code=status.HTTP_200_OK,
    summary="Obtener Métricas del Dashboard (RF-020)",
    description="Retorna el conteo acumulado de tickets agrupado por estado filtrado por fechas.",
    dependencies=[Depends(RoleChecker(["Administrador"]))]
)
async def get_dashboard_metrics(
    start_date: str = Query(None, description="Fecha de inicio (YYYY-MM-DD)"),
    end_date: str = Query(None, description="Fecha de fin (YYYY-MM-DD)"),
    period: str = Query(None, description="Período mensual (YYYY-MM)")
):
    s_dt, e_dt = resolve_date_range(start_date, end_date, period)
    status_counts = await DashboardDAO.get_monthly_status_metrics(s_dt, e_dt)
    critical_sla_count = await DashboardDAO.get_critical_sla_count()
    recent_logs = await LogDAO.get_recent(5)
    
    logger.debug("Métricas del dashboard solicitadas con éxito.")
    response_data = {
        "status_counts": status_counts,
        "critical_sla_count": critical_sla_count,
        "recent_logs": recent_logs
    }
    # El estado de fusión cuenta directamente en la raíz para una compatibilidad de prueba heredada del 100 %.
    response_data.update(status_counts)
    return response_data

@router.get(
    "/logs",
    status_code=status.HTTP_200_OK,
    summary="Obtener Logs de Auditoría",
    description="Retorna el listado completo de transiciones de estados para auditoría filtrado por fechas.",
    dependencies=[Depends(RoleChecker(["Administrador"]))]
)
async def get_audit_logs(
    start_date: str = Query(None, description="Fecha de inicio (YYYY-MM-DD)"),
    end_date: str = Query(None, description="Fecha de fin (YYYY-MM-DD)"),
    period: str = Query(None, description="Período mensual (YYYY-MM)")
):
    s_dt, e_dt = resolve_date_range(start_date, end_date, period)
    return await LogDAO.get_all(s_dt, e_dt)

@router.get(
    "/analytics/capacity-projection",
    status_code=status.HTTP_200_OK,
    summary="RF-026: Proyección de Capacidad Técnica Operativa e Infraestructura",
    description="Retorna la proyección de demanda de incidentes por especialidad y alertas de contratación.",
    dependencies=[Depends(RoleChecker(["Administrador"]))]
)
async def get_capacity_projection(
    months: int = Query(3, ge=3, description="Número de meses históricos para el análisis de proyección (mínimo 3).")
):
    projection_data = await DashboardDAO.get_capacity_projection(months)
    logger.info(f"Proyección de capacidad solicitada para {months} meses.")
    return projection_data

@router.get(
    "/analytics/churn-risk",
    status_code=status.HTTP_200_OK,
    summary="RF-025: Alerta Temprana de Churn",
    description="Retorna un listado de organizaciones con riesgo inminente de abandono (churn) "
                "basado en violaciones de SLA y baja satisfacción en los últimos 14 días.",
    dependencies=[Depends(RoleChecker(["Administrador"]))]
)
async def get_churn_risk_alert():
    churn_risk_organizations = await DashboardDAO.get_churn_risk_alerts()
    logger.info("Alerta temprana de churn solicitada y procesada.")
    return churn_risk_organizations

@router.get(
    "/organizations-by-ticket-count",
    status_code=status.HTTP_200_OK,
    summary="Obtener organizaciones por rango de tickets acumulados",
    description="Retorna un listado de organizaciones con su respectivo conteo de tickets acumulados, "
                "filtrado por un rango opcional [tickets_min, tickets_max].",
    dependencies=[Depends(RoleChecker(["Administrador"]))]
)
async def get_organizations_by_ticket_count(
    tickets_min: Optional[int] = Query(None, description="Cantidad mínima de tickets acumulados"),
    tickets_max: Optional[int] = Query(None, description="Cantidad máxima de tickets acumulados")
):
    logger.info(f"Filtro de organizaciones por rango de tickets: min={tickets_min}, max={tickets_max}")
    return await DashboardDAO.get_organizations_by_ticket_count(tickets_min, tickets_max)