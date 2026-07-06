from datetime import datetime
from backend.config.database import Database

class ReportDAO:
    @classmethod
    async def get_mttr_report(cls, start_date: datetime, end_date: datetime) -> list:
        """
        RF-019: Generates MTTR analytics grouping closed/resolved tickets by technician
        and calculating resolved volume and average resolution duration (MTTR) in minutes.
        """
        db = Database.get_db()
        pipeline = [
            # 1. Partidos de tickets cerrados/resueltos dentro del rango de fechas que tengan asignado un técnico
            {
                "$match": {
                    "status": {"$in": ["Cerrado", "Resuelto"]},
                    "resuelto_at": {"$gte": start_date, "$lte": end_date},
                    "assigned_tech_id": {"$ne": None}
                }
            },
            # 2. Duración de la resolución del proyecto en milisegundos
            {
                "$project": {
                    "assigned_tech_id": 1,
                    "assigned_tech_name": 1,
                    "duration_ms": {"$subtract": ["$resuelto_at", "$created_at"]}
                }
            },
            # 3. Agrupar por técnico y sumar tiempos de resolución
            {
                "$group": {
                    "_id": "$assigned_tech_id",
                    "tech_name": {"$first": "$assigned_tech_name"},
                    "volumen_resuelto": {"$sum": 1},
                    "total_duration_ms": {"$sum": "$duration_ms"}
                }
            },
            # 4. Detalles finales del proyecto, convirtiendo la duración total a MTTR en minutos.
            {
                "$project": {
                    "tech_id": "$_id",
                    "tech_name": {"$ifNull": ["$tech_name", "Desconocido"]},
                    "volumen_resuelto": 1,
                    "mttr_minutes": {
                        "$cond": {
                            "if": {"$gt": ["$volumen_resuelto", 0]},
                            "then": {
                                "$round": [
                                    {"$divide": [{"$divide": ["$total_duration_ms", 60000]}, "$volumen_resuelto"]},
                                    2
                                ]
                            },
                            "else": 0
                        }
                    }
                }
            }
        ]
        
        cursor = db["tickets"].aggregate(pipeline)
        return await cursor.to_list(length=None)