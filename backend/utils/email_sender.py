import asyncio
import logging
import os

logger = logging.getLogger("techhelp.email")

# URL del frontend — se lee desde variable de entorno en producción
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")


async def send_activation_email(email: str, name: str):
    """
    Simulates sending an activation email to a new client user.
    Introduces a simulated network/SMTP latency delay of 2 seconds.
    Designed to run asynchronously in a BackgroundTask.
    """
    logger.info(f"Iniciando simulación de envío de correo de activación para {name} <{email}>...")
    
    # Latencia similar de red (2 segundos)
    await asyncio.sleep(2)
    
    logger.info(f"Correo de activación enviado exitosamente a {email}. Código de activación generado.")

async def send_survey_email(email: str, ticket_code: str, token: str):
    """
    Simulates sending a survey email to the client user.
    Introduces a simulated network/SMTP latency delay of 2 seconds.
    Designed to run asynchronously in a BackgroundTask or asyncio task.
    """
    logger.info(f"Iniciando simulación de envío de encuesta para ticket {ticket_code} a <{email}>...")
    await asyncio.sleep(2)
    survey_url = f"{FRONTEND_URL}/feedback?token={token}"
    logger.info(f"Correo de encuesta enviado exitosamente a {email}. URL de evaluación: {survey_url}")

async def send_comment_notification_email(email: str, ticket_code: str, ticket_id: str):
    """
    Simulates sending an email notification to the client when a new public comment is added.
    Introduces a simulated network/SMTP latency delay of 2 seconds.
    """
    logger.info(f"Iniciando simulación de envío de notificación de nota pública para ticket {ticket_code} a <{email}>...")
    await asyncio.sleep(2)
    ticket_url = f"{FRONTEND_URL}/tickets/{ticket_id}"
    logger.info(f"Correo de notificación enviado exitosamente a {email}. URL del ticket: {ticket_url}")