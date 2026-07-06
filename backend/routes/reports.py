import io
import csv
import logging
from datetime import datetime
from fastapi import APIRouter, status, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from backend.dao.report_dao import ReportDAO
from backend.security.auth import RoleChecker

logger = logging.getLogger("techhelp.routes.reports")

router = APIRouter(
    prefix="/reports",
    tags=["Reports"]
)

def iter_csv(data: list):
    """
    Generator helper that formats report records into CSV rows on-the-fly.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Escribir encabezado
    writer.writerow(["ID Tecnico", "Nombre Tecnico", "Volumen Resuelto", "MTTR (Minutos)"])
    yield output.getvalue()
    output.seek(0)
    output.truncate(0)
    
    # Escribir filas del cuerpo
    for row in data:
        writer.writerow([
            row["tech_id"],
            row["tech_name"],
            row["volumen_resuelto"],
            row["mttr_minutes"]
        ])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

@router.get(
    "/mttr",
    status_code=status.HTTP_200_OK,
    summary="Generar Reporte MTTR de Técnicos (RF-019)",
    description="Genera y descarga un archivo CSV con las métricas de volumen y MTTR (Tiempo Medio de Reparación) de técnicos.",
    dependencies=[Depends(RoleChecker(["Administrador"]))]
)
async def get_mttr_report(
    fecha_inicio: str = Query(..., description="Fecha de inicio en formato ISO (YYYY-MM-DD o YYYY-MM-DDTHH:MM:SS)"),
    fecha_fin: str = Query(..., description="Fecha de fin en formato ISO (YYYY-MM-DD o YYYY-MM-DDTHH:MM:SS)")
):
    try:
        start_dt = datetime.fromisoformat(fecha_inicio.replace(" ", "+").replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(fecha_fin.replace(" ", "+").replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fechas inválido. Utilice formato ISO 8601.")
        
    if start_dt > end_dt:
        raise HTTPException(status_code=400, detail="Rango de fechas inválido: fecha_inicio es posterior a fecha_fin.")
        
    report_data = await ReportDAO.get_mttr_report(start_dt, end_dt)
    
    return StreamingResponse(
        iter_csv(report_data),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="reporte_mttr.csv"'}
    )