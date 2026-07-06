import secrets
from datetime import datetime, timezone, timedelta
from backend.config.database import Database

async def generate_survey_token(ticket_id: str, customer_email: str, tech_id: str, tech_name: str) -> str:
    """
    Generates a unique cryptographic survey token valid for 48 hours,
    persisting it to the database for subsequent evaluation validation.
    """
    db = Database.get_db()
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=48)
    
    doc = {
        "token": token,
        "ticket_id": ticket_id,
        "customer_email": customer_email,
        "tech_id": tech_id,
        "tech_name": tech_name,
        "expires_at": expires_at,
        "used": False
    }
    
    await db["survey_tokens"].insert_one(doc)
    return token