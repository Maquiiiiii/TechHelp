from datetime import datetime, timezone
from typing import Optional
from fastapi import HTTPException
from pymongo.errors import OperationFailure, PyMongoError

from backend.config.database import Database
from backend.dto.ticket_dto import AuditLogDTO

class LogDAO:
    collection_name = "audit_logs"

    @classmethod
    def _get_collection(cls):
        """Async database collection accessor."""
        db = Database.get_db()
        return db[cls.collection_name]

    @classmethod
    async def registrar_evento_forense(cls, log_data: AuditLogDTO):
        """
        RF-014 / RNF-SEG-004: Persiste un evento de auditoría forense en la colección inmutable 'audit_logs'.

        Utiliza un rol de base de datos restringido que solo permite acciones 'insert' y 'find'.
        Si se intenta una operación no permitida (ej. update, delete), MongoDB la rechazará.

        - Intercepta 'OperationFailure' (violación de permisos) y la convierte en un HTTP 403 Forbidden.
        - Propaga cualquier otro 'PyMongoError' para ser manejado por el middleware global de errores,
          evitando la fuga de detalles de la base de datos al cliente.

        Args:
            log_data (AuditLogDTO): Objeto Pydantic con los datos del evento a registrar.

        Raises:
            HTTPException(403): Si la operación es denegada por falta de privilegios en la BD.
            PyMongoError: Para cualquier otro error de base de datos durante la inserción.
        """
        collection = cls._get_collection()
        log_entry = log_data.model_dump()

        try:
            result = await collection.insert_one(log_entry)
            return str(result.inserted_id)
        except OperationFailure as e:
            # Error de permisos: el rol no permite esta acción (ej. actualizar/eliminar)
            raise HTTPException(
                status_code=403,
                detail=f"Acción prohibida. Violación de la política de inmutabilidad en la bitácora de auditoría. Causa: {e.details.get('errmsg') if e.details else str(e)}"
            )
        except PyMongoError as e:
            # Otro error de base de datos (ej. problema de conexión, tiempo de espera)
            # Se propaga para que el error_handler.py lo capture y devuelva un 500 genérico.
            raise e

    @classmethod
    async def get_all(cls, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> list:
        """
        Consulta los logs de auditoría, opcionalmente filtrando por un rango de fechas.
        Los resultados se ordenan del más reciente al más antiguo.
        """
        collection = cls._get_collection()
        query = {}
        if start_date or end_date:
            query["timestamp"] = {}
            if start_date:
                query["timestamp"]["$gte"] = start_date
            if end_date:
                query["timestamp"]["$lte"] = end_date

        cursor = collection.find(query).sort("timestamp", -1)
        logs = await cursor.to_list(length=1000)  # Limite a 1000 para evitar sobrecarga
        for log in logs:
            log["_id"] = str(log["_id"])  # Convertir ObjectId en una cadena para serialización JSON
            if "valor_anterior" in log:
                log["estado_anterior"] = log["valor_anterior"]
            if "nuevo_valor" in log:
                log["estado_nuevo"] = log["nuevo_valor"]
        return logs

    @classmethod
    async def get_recent(cls, limit: int = 5) -> list:
        """
        Consulta los N logs de auditoría más recientes.
        """
        collection = cls._get_collection()
        cursor = collection.find({}).sort("timestamp", -1).limit(limit)
        logs = await cursor.to_list(length=limit)
        for log in logs:
            log["_id"] = str(log["_id"])  # Convertir ObjectId en una cadena para serialización JSON
            if "valor_anterior" in log:
                log["estado_anterior"] = log["valor_anterior"]
            if "nuevo_valor" in log:
                log["estado_nuevo"] = log["nuevo_valor"]
        return logs

# Exporte el alias para seguir siendo compatible con las referencias heredadas de AuditLogDAO
AuditLogDAO = LogDAO