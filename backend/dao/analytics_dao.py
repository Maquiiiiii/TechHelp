from datetime import datetime, timezone, timedelta
from backend.config.database import Database

class AnalyticsDAO:
    @classmethod
    async def get_churn_risk_report(cls) -> list:
        """
        RF-025: Aggregation pipeline for Churn Risk early warning alert.
        Delegates to DashboardDAO.get_churn_risk_alerts for unified business logic.
        """
        from backend.dao.dashboard_dao import DashboardDAO
        return await DashboardDAO.get_churn_risk_alerts()

    @classmethod
    async def get_capacity_projections(cls, range_months: int) -> list:
        """
        RF-026: Aggregates closed tickets chronologically monthly by Specialty Category.
        """
        db = Database.get_db()
        start_date = datetime.now(timezone.utc) - timedelta(days=range_months * 30)
        
        pipeline = [
            # 1. Coincidir con los boletos de estado de Cerrado dentro del rango histórico
            {
                "$match": {
                    "status": "Cerrado",
                    "created_at": {"$gte": start_date}
                }
            },
            # 2. Agrupar por mes-año y categoría
            {
                "$group": {
                    "_id": {
                        "year": {"$year": "$created_at"},
                        "month": {"$month": "$created_at"},
                        "categoria": "$categoria"
                    },
                    "count": {"$sum": 1}
                }
            },
            # 3. Formatear la etiqueta de fecha
            {
                "$project": {
                    "_id": 0,
                    "categoria": "$_id.categoria",
                    "year_month": {
                        "$concat": [
                            {"$toString": "$_id.year"},
                            "-",
                            {"$cond": [{"$lt": ["$_id.month", 10]}, "0", ""]},
                            {"$toString": "$_id.month"}
                        ]
                    },
                    "count": 1,
                    "year": "$_id.year",
                    "month": "$_id.month"
                }
            },
            # 4. Ordenar cronológicamente
            {
                "$sort": {"year": 1, "month": 1}
            }
        ]
        
        cursor = db["tickets"].aggregate(pipeline)
        return await cursor.to_list(length=None)