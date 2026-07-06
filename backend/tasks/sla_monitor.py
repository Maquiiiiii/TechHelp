import asyncio
import logging
from datetime import datetime, timezone, timedelta
from backend.config.database import Database

logger = logging.getLogger("techhelp.tasks.sla_monitor")

def is_5_business_days_passed(from_date: datetime) -> bool:
    """
    Checks if at least 5 business days (Monday to Friday) have passed since from_date.
    """
    now = datetime.now(timezone.utc)
    if from_date.tzinfo is None:
        from_date = from_date.replace(tzinfo=timezone.utc)
    
    delta_days = (now - from_date).days
    if delta_days < 5:
        return False
        
    business_days = 0
    temp_date = from_date
    while temp_date < now:
        if temp_date.weekday() < 5:  # lunes a viernes
            business_days += 1
        temp_date += timedelta(days=1)
        
    return business_days >= 5

async def check_sla_breaches():
    """
    RF-015 SLA Monitor logic:
    Finds tickets in status 'Asignado' or 'En Proceso' with priority 'Alta' and check
    if their net attention duration (elapsed time since creation minus the ticket's 
    accumulated minutos_en_espera_acumulados) exceeds 120 minutes.
    """
    db = Database.get_db()
    if db is None:
        return

    tickets_col = db["tickets"]
    query = {
        "status": {"$in": ["Asignado", "En Proceso"]},
        "prioridad": "Alta",
        "sla_vencido": {"$ne": True}
    }

    cursor = tickets_col.find(query)
    tickets = await cursor.to_list(length=None)
    now = datetime.now(timezone.utc)

    for ticket in tickets:
        created_at = ticket.get("created_at")
        if created_at and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        total_elapsed_minutes = (now - created_at).total_seconds() / 60
        paused_minutes = ticket.get("minutos_en_espera_acumulados", 0.0)
        net_attention_minutes = total_elapsed_minutes - paused_minutes

        if net_attention_minutes > 120:
            logger.warning(
                f"SLA BREACH DETECTED: Ticket {ticket.get('code')} has been active for {net_attention_minutes:.2f} "
                f"net minutes."
            )
            await tickets_col.update_one(
                {"_id": ticket["_id"]},
                {
                    "$set": {"sla_vencido": True},
                    "$inc": {"__v": 1}
                }
            )

async def auto_close_resolved_tickets():
    """
    Sweeps database for tickets that have been in status 'Resuelto'
    for at least 5 business days without any new comments from the client,
    and automatically closes them.
    """
    db = Database.get_db()
    if db is None:
        return

    tickets_col = db["tickets"]
    query = {"status": "Resuelto"}
    
    cursor = tickets_col.find(query)
    tickets = await cursor.to_list(length=None)
    
    for ticket in tickets:
        # Obtenga todos los comentarios escritos por un cliente.
        client_comments = [c for c in ticket.get("comentarios", []) if c.get("rol_autor") == "Cliente"]
        
        if client_comments:
            # Encuentre la marca de tiempo del último comentario del cliente.
            latest_comment = max(client_comments, key=lambda x: x.get("timestamp"))
            baseline_date = latest_comment.get("timestamp")
        else:
            baseline_date = ticket.get("resuelto_at") or ticket.get("created_at")
            
        if baseline_date:
            if baseline_date.tzinfo is None:
                baseline_date = baseline_date.replace(tzinfo=timezone.utc)
                
            if is_5_business_days_passed(baseline_date):
                ticket_id_str = str(ticket["_id"])
                logger.info(f"Auto-closing resolved ticket {ticket.get('code')} (baseline date: {baseline_date})")
                
                # Actualizar el estado del ticket a través de TicketDAO (activa registros de auditoría y envío de encuestas)
                from backend.dao.ticket_dao import TicketDAO
                try:
                    await TicketDAO.update_status(
                        ticket_id=ticket_id_str,
                        current_version=ticket.get("__v", 0),
                        new_status="Cerrado",
                        ip_origen="127.0.0.1"
                    )
                except Exception as e:
                    logger.error(f"Error auto-closing ticket {ticket.get('code')}: {str(e)}")

async def start_sla_monitor_loop():
    """Background loop that runs every 5 minutes (300 seconds) to check SLA and auto-close resolved tickets."""
    logger.info("Monitor de vencimientos de SLA (RF-015) y Auto-cierre de tickets iniciado en segundo plano.")
    while True:
        try:
            await check_sla_breaches()
            await auto_close_resolved_tickets()
        except Exception as e:
            logger.error(f"Error ejecutando tareas en segundo plano (SLA/Auto-cierre): {str(e)}", exc_info=True)
        await asyncio.sleep(300)