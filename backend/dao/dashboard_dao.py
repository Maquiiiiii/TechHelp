from datetime import datetime, timezone, timedelta
from backend.config.database import Database

class DashboardDAO:
    collection_name = "tickets"

    @classmethod
    def get_collection(cls):
        """Async database collection accessor."""
        db = Database.get_db()
        return db[cls.collection_name]

    @classmethod
    async def get_monthly_status_metrics(cls, start_date: datetime, end_date: datetime) -> dict:
        """
        RF-020 status metrics:
        Retrieves ticket counts grouped by status for a specific date range.
        Utilizes a native MongoDB aggregation pipeline ($match and $group) for optimal performance.
        """
        collection = cls.get_collection()
        
        pipeline = [
            # 1. Coincidir únicamente con los boletos creados en el rango
            {
                "$match": {
                    "created_at": {
                        "$gte": start_date,
                        "$lte": end_date
                    }
                }
            },
            # 2. Agrupar por estado y recuento de sumas
            {
                "$group": {
                    "_id": "$status",
                    "count": {"$sum": 1}
                }
            }
        ]
        
        cursor = collection.aggregate(pipeline)
        items = await cursor.to_list(length=None)
        
        # Asigne los resultados sin procesar de la lista de agregación de MongoDB al dictado de clave-valor: {estado: recuento}
        metrics = {item["_id"]: item["count"] for item in items}
        
        # Asegúrese de que todos los estados posibles del ticket estén incluidos con el reinicio predeterminado de 0
        allowed_statuses = ["Abierto", "Asignado", "En Proceso", "En Espera", "Resuelto", "Cerrado"]
        for status in allowed_statuses:
            if status not in metrics:
                metrics[status] = 0
                
        return metrics

    @classmethod
    async def get_critical_sla_count(cls) -> int:
        """
        Count active tickets whose SLA is expiring within 1 hour.
        """
        collection = cls.get_collection()
        now = datetime.now(timezone.utc)
        one_hour_later = now + timedelta(hours=1)

        query = {
            "status": {"$in": ["Abierto", "Asignado", "En Proceso", "En Espera"]},
            "fecha_expiracion_sla": { # Campo corregido para usar la fecha y hora de vencimiento real.
                "$gte": now,
                "$lte": one_hour_later
            }
        }
        return await collection.count_documents(query)

    @classmethod
    async def get_capacity_projection(cls, months: int) -> dict:
        """
        RF-026: Proyección de Capacidad Técnica Operativa e Infraestructura.
        Calcula la proyección de demanda de incidentes por especialidad y la compara con la capacidad.
        Retorna datos para gráficos y alertas de contratación.
        Esta es una simulación simplificada de la lógica de regresión lineal.
        """
        db = Database.get_db()
        tickets_collection = db["tickets"]
        technicians_collection = db["technicians"]

        # Asegurar un mínimo de 3 meses de histórico para el análisis.
        if months < 3:
            months = 3

        # Calcular la fecha de inicio para el período de análisis
        start_date = datetime.now(timezone.utc) - timedelta(days=months * 30) # Aproximación de meses
        
        # --- Pipeline para obtener tendencias históricas de incidentes por especialidad ---
        incident_trend_pipeline = [
            {"$match": {"created_at": {"$gte": start_date}}},
            {"$group": {
                "_id": {
                    "specialty": "$categoria",
                    "month": {"$dateToString": {"format": "%Y-%m", "date": "$created_at"}}
                },
                "incident_count": {"$sum": 1}
            }},
            {"$group": {
                "_id": "$_id.month",
                "specialties": {
                    "$push": {
                        "specialty": "$_id.specialty",
                        "count": "$incident_count"
                    }
                }
            }},
            {"$sort": {"_id": 1}} # Ordenar por mes ascendente
        ]
        incident_trends_cursor = tickets_collection.aggregate(incident_trend_pipeline)
        incident_trends = await incident_trends_cursor.to_list(length=None)

        # --- Calcular la capacidad actual por especialidad ---
        # Simplificación: Asumimos que un técnico puede manejar X tickets por mes.
        # La capacidad es (número de técnicos * X).
        # Para este ejemplo, asumimos 20 tickets/mes por técnico.
        capacity_per_tech = 20 
        
        tech_specialties_cursor = technicians_collection.aggregate([
            {"$group": {
                "_id": "$especialidad",
                "tech_count": {"$sum": 1}
            }}
        ])
        tech_capacities = {
            item["_id"]: item["tech_count"] * capacity_per_tech
            for item in await tech_specialties_cursor.to_list(length=None)
        }

        # --- Combinar datos y simular proyección/alertas ---
        projection_data = []
        hiring_alerts = []
        
        # Obtener todas las especialidades únicas
        all_specialties = set()
        for trend in incident_trends:
            for s in trend["specialties"]:
                all_specialties.add(s["specialty"])
        all_specialties.update(tech_capacities.keys())

        # Generar todos los meses en el rango para datos consistentes del gráfico.
        current_month_dt = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        months_list = []
        for i in range(months):
            month_str = (current_month_dt - timedelta(days=i * 30)).strftime("%Y-%m")
            months_list.insert(0, month_str) # Insertar al principio para mantener el orden ascendente

        for month_str in months_list:
            month_data = {"month": month_str}
            
            trend_for_month = next((t for t in incident_trends if t["_id"] == month_str), None)
            
            for specialty in all_specialties:
                incident_count = 0
                if trend_for_month:
                    specialty_trend = next((s for s in trend_for_month["specialties"] if s["specialty"] == specialty), None)
                    if specialty_trend:
                        incident_count = specialty_trend["count"]
                
                month_data[f"{specialty}_incidents"] = incident_count
                month_data[f"{specialty}_capacity"] = tech_capacities.get(specialty, 0) # Capacidad para esta especialidad

            projection_data.append(month_data)

        # --- Alertas de contratación similares basadas en la regla de negocio (RF-026) ---
        # "incremento sostenido de la demanda mayor al 20% mensual"
        # "si la demanda supera los límites saludables"
        
        # Para simplificar, si la demanda del último mes es > 80% de la capacidad y ha crecido > 20% respecto al mes anterior.
        if len(projection_data) >= 2:
            second_to_last_month_data = projection_data[-2]
            last_month_data = projection_data[-1]
            
            for specialty in all_specialties:
                incidents_prev = second_to_last_month_data.get(f"{specialty}_incidents", 0)
                incidents_curr = last_month_data.get(f"{specialty}_incidents", 0)
                capacity = tech_capacities.get(specialty, 0)

                if capacity > 0: # Solo si hay capacidad definida
                    growth_rate = 0.0
                    if incidents_prev > 0:
                        growth_rate = (incidents_curr - incidents_prev) / incidents_prev
                    elif incidents_curr > 0: # Si no había incidentes antes pero ahora sí
                        growth_rate = 1.0 # Considerar un crecimiento muy alto

                    # Condición de alerta: crecimiento > 20% Y utilización de capacidad > 70%
                    if growth_rate > 0.20 and incidents_curr > (capacity * 0.70):
                        hiring_alerts.append({
                            "specialty": specialty,
                            "reason": f"La demanda de incidentes de {specialty} ha crecido un {growth_rate*100:.0f}% en el último mes y está utilizando el {incidents_curr/capacity*100:.0f}% de la capacidad. Se recomienda contratación inmediata.",
                            "needs_hiring": True
                        })
                elif incidents_curr > 0: # Si no hay técnicos para una especialidad pero hay incidentes
                     hiring_alerts.append({
                        "specialty": specialty,
                        "reason": f"No hay técnicos asignados a la especialidad de {specialty} pero se han registrado {incidents_curr} incidentes. Se recomienda contratación inmediata.",
                        "needs_hiring": True
                    })

        return {
            "projection_data": projection_data,
            "hiring_alerts": hiring_alerts
        }

    @classmethod
    async def get_churn_risk_alerts(cls) -> list:
        """
        RF-025: Panel Analítico Predictivo de Alerta Temprana de Churn.
        Calcula alertas tempranas de churn basadas en la tasa de violación de SLA (>15%)
        y promedio de satisfacción (<2.5) en los últimos 14 días.
        """
        db = Database.get_db()
        tickets_collection = db["tickets"]
        fourteen_days_ago = datetime.now(timezone.utc) - timedelta(days=14)
        
        pipeline = [
            # 1. Entradas para partidos creados en los últimos 14 días
            {
                "$match": {
                    "created_at": {"$gte": fourteen_days_ago}
                }
            },
            # 2. Agregue la cadena ticket_id y determine si se viola el SLA
            {
                "$addFields": {
                    "ticket_id_str": {"$toString": "$_id"},
                    "sla_violado": {
                        "$cond": [
                            {
                                "$or": [
                                    {"$eq": ["$sla_vencido", True]},
                                    {
                                        "$and": [
                                            {"$ifNull": ["$fecha_expiracion_sla", False]},
                                            {
                                                "$or": [
                                                    {"$gt": ["$resuelto_at", "$fecha_expiracion_sla"]},
                                                    {
                                                        "$and": [
                                                            {"$not": [{"$ifNull": ["$resuelto_at", False]}]},
                                                            {"$gt": [datetime.now(timezone.utc), "$fecha_expiracion_sla"]}
                                                        ]
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            },
                            1,
                            0
                        ]
                    }
                }
            },
            # 3. Buscar comentarios de satisfaccion_cliente
            {
                "$lookup": {
                    "from": "satisfaccion_cliente",
                    "localField": "ticket_id_str",
                    "foreignField": "ticket_id",
                    "as": "feedback"
                }
            },
            # 4. Extraer puntuación de calificación de comentarios
            {
                "$addFields": {
                    "feedback_score": {"$arrayElemAt": ["$feedback.valoracion", 0]}
                }
            },
            # 5. Agrupar por id_cliente/organización
            {
                "$group": {
                    "_id": "$customer_id",
                    "total_tickets": {"$sum": 1},
                    "sla_violations": {"$sum": "$sla_violado"},
                    "average_survey_rating": {"$avg": "$feedback_score"}
                }
            },
            # 6. Calcular el porcentaje
            {
                "$addFields": {
                    "sla_violation_percentage": {
                        "$cond": [
                            {"$gt": ["$total_tickets", 0]},
                            {"$multiply": [{"$divide": ["$sla_violations", "$total_tickets"]}, 100]},
                            0.0
                        ]
                    }
                }
            },
            # 7. Buscar información de la organización (cruzar para Razón Social, RUT y Email)
            {
                "$lookup": {
                    "from": "organizations",
                    "localField": "_id",
                    "foreignField": "rut",
                    "as": "org_info"
                }
            },
            {"$unwind": "$org_info"},
            # 8. Proyectar campos y calcular riesgo_inminente
            {
                "$project": {
                    "_id": 0,
                    "customer_id": "$org_info.rut",
                    "organization_name": "$org_info.name",
                    "organization_rut": "$org_info.rut",
                    "organization_email": "$org_info.email",
                    "total_tickets": 1,
                    "tasa_violacion_sla": {"$divide": ["$sla_violation_percentage", 100.0]},
                    "satisfaccion_promedio": "$average_survey_rating",
                    "sla_violation_percentage": {"$round": ["$sla_violation_percentage", 2]},
                    "average_survey_rating": {"$round": ["$average_survey_rating", 2]},
                    "riesgo_inminente": {
                        "$and": [
                            {"$gt": ["$sla_violation_percentage", 15.0]},
                            {
                                "$and": [
                                    {"$ne": ["$average_survey_rating", None]},
                                    {"$lt": ["$average_survey_rating", 2.5]}
                                ]
                            }
                        ]
                    },
                    "riesgo_inminente_cancelacion": {
                        "$and": [
                            {"$gt": ["$sla_violation_percentage", 15.0]},
                            {
                                "$and": [
                                    {"$ne": ["$average_survey_rating", None]},
                                    {"$lt": ["$average_survey_rating", 2.5]}
                                ]
                            }
                        ]
                    }
                }
            },
            # 9. Ordenar por porcentaje de violación de SLA de manera descendente
            {"$sort": {"sla_violation_percentage": -1, "average_survey_rating": 1}}
        ]
        
        cursor = tickets_collection.aggregate(pipeline)
        return await cursor.to_list(length=None)

    @classmethod
    async def obtener_alerta_temprana_churn(cls) -> list:
        """Alias for legacy endpoint compatibility."""
        return await cls.get_churn_risk_alerts()

    @classmethod
    async def get_organizations_by_ticket_count(cls, tickets_min: int = None, tickets_max: int = None) -> list:
        """
        Retrieves a list of organizations with their associated ticket counts,
        filtered optionally by a range of ticket counts [tickets_min, tickets_max].
        Ensures explicit serialization of ObjectId and conversion of dates for safety.
        """
        db = Database.get_db()
        org_collection = db["organizations"]

        pipeline = [
            # 1. Busque tickets asociados utilizando tickets de coincidencia de rutas organizacionales customer_id
            {
                "$lookup": {
                    "from": "tickets",
                    "localField": "rut",
                    "foreignField": "customer_id",
                    "as": "tickets_asociados"
                }
            },
            # 2. Agregue el tamaño de asignación del campo tickets_count de la matriz de tickets asociada
            {
                "$addFields": {
                    "tickets_count": {"$size": "$tickets_asociados"}
                }
            }
        ]

        # 3. Cree una etapa de coincidencia condicional para el rango de recuento de entradas
        match_conditions = {}
        if tickets_min is not None:
            match_conditions["$gte"] = tickets_min
        if tickets_max is not None:
            match_conditions["$lte"] = tickets_max

        if match_conditions:
            pipeline.append({
                "$match": {
                    "tickets_count": match_conditions
                }
            })

        # 4. Proyecte solo campos limpios y relevantes
        pipeline.append({
            "$project": {
                "_id": 1,
                "name": 1,
                "rut": 1,
                "email": 1,
                "email_corporativo": 1,
                "razon_social": 1,
                "tier_contractual": 1,
                "customer_id": 1,
                "industria": 1,
                "__v": 1,
                "created_at": 1,
                "tickets_count": 1
            }
        })

        # 5. Ordene por tickets_count descendente para obtener una mejor descripción analítica
        pipeline.append({
            "$sort": {"tickets_count": -1, "name": 1}
        })

        cursor = org_collection.aggregate(pipeline)
        docs = await cursor.to_list(length=None)

        # 6. ObjectId explícito para convertir cadenas para evitar errores de serialización
        for doc in docs:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
            # Formatear fecha y hora
            if "created_at" in doc and isinstance(doc["created_at"], datetime):
                doc["created_at"] = doc["created_at"].isoformat()

        return docs