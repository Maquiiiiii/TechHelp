import secrets
from datetime import datetime, timezone
from backend.config.database import Database
from backend.middlewares.error_handler import AppError

class TransbankService:
    @classmethod
    async def initiate_transaction(cls, organization_id: str, amount: float) -> dict:
        """
        RNF-COM-007: Initiates a simulated Webpay Plus payment transaction.
        Generates a token and returns redirection URL. Saves state to DB.
        """
        db = Database.get_db()
        token = secrets.token_hex(32)
        redirect_url = f"https://webpay3g.transbank.cl/rswebpaytransaction/api/webpay/v1.2/js/pago.html?token={token}"
        
        doc = {
            "token": token,
            "organization_id": organization_id,
            "amount": amount,
            "status": "Creado",
            "created_at": datetime.now(timezone.utc)
        }
        
        await db["billing_transactions"].insert_one(doc)
        
        return {
            "token": token,
            "redirect_url": redirect_url,
            "amount": amount,
            "organization_id": organization_id,
            "status": "Creado"
        }

    @classmethod
    async def confirm_transaction(cls, token: str) -> dict:
        """
        RNF-COM-007: Confirms a simulated Webpay Plus payment transaction.
        Validates the token and updates the invoice state to 'Pagado'.
        """
        db = Database.get_db()
        tx = await db["billing_transactions"].find_one({"token": token})
        
        if not tx:
            raise AppError("Token de transacción inválido o inexistente.", status_code=404)
            
        if tx.get("status") == "Pagado":
            raise AppError("Esta transacción ya ha sido pagada previamente.", status_code=400)
            
        # Actualizar el estado de la transacción a Pagado
        await db["billing_transactions"].update_one(
            {"_id": tx["_id"]},
            {"$set": {
                "status": "Pagado",
                "confirmed_at": datetime.now(timezone.utc)
            }}
        )
        
        tx["status"] = "Pagado"
        return tx