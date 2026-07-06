import random
import logging
from datetime import datetime, timezone
from bson import ObjectId

logger = logging.getLogger("techhelp.dao.tickets")
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from backend.config.database import Database
from backend.middlewares.error_handler import ConcurrencyError, AppError
from backend.dao.log_dao import LogDAO
from backend.dto.ticket_dto import AuditLogDTO

class TicketDAO:
    collection_name = "tickets"

    @classmethod
    def get_collection(cls):
        """Async database collection accessor."""
        db = Database.get_db()
        return db[cls.collection_name]

    @classmethod
    async def create_indexes(cls):
        """Create database indexes. Index 'code' must be unique. Index 'customer_id' serves as shard key."""
        collection = cls.get_collection()
        await collection.create_index("code", unique=True)
        await collection.create_index("customer_id")

    @classmethod
    async def _generate_unique_code(cls) -> str:
        """Helper to generate a unique code in format TK-XXXXX (RF-005)."""
        collection = cls.get_collection()
        for _ in range(10):  # Reintentar bucle para evitar colisiones bajo carga alta
            random_num = random.randint(10000, 99999)
            code = f"TK-{random_num}"
            # Comprueba si este código ya existe
            exists = await collection.find_one({"code": code})
            if not exists:
                return code
        raise AppError("No se pudo generar un código único de ticket en 10 intentos.", status_code=500)

    @classmethod
    async def create(cls, title: str, description: str, customer_id: str, categoria: str, prioridad: str) -> dict:
        """
        Create a new support ticket in MongoDB.
        Generates a unique TK-XXXXX code and initializes status to 'Abierto' and OCC __v to 0.
        """
        collection = cls.get_collection()
        
        # Verifique que la organización del cliente exista antes de crear el ticket
        from backend.dto.organization_dto import validate_chilean_rut
        try:
            normalized_customer_id = validate_chilean_rut(customer_id)
        except Exception:
            normalized_customer_id = customer_id

        db = Database.get_db()
        org_exists = await db["organizations"].find_one({"rut": normalized_customer_id})
        if not org_exists:
            raise AppError(f"La organización cliente con RUT {customer_id} no existe (RF-002).", status_code=404)

        # RF-024: Obtener el nivel contractual de la organización para cálculo de SLA
        tier_contractual = org_exists.get("tier_contractual", "Bronce")
        from backend.utils.sla_matrix import get_sla_window
        from datetime import timedelta
        created_time = datetime.now(timezone.utc)

        # RF-024: Regla de Excepción para Nivel Oro + Prioridad Alta
        if prioridad == "Alta" and tier_contractual == "Oro":
            sla_window = 30  # 30 minutos para Nivel Oro y Prioridad Alta
        else:
            # Cálculo estándar de SLA basado en nivel y prioridad
            sla_window = get_sla_window(tier_contractual, prioridad)
            
        fecha_expiracion_sla = created_time + timedelta(minutes=sla_window)

        code = await cls._generate_unique_code()
        
        document = {
            "code": code,
            "title": title,
            "description": description,
            "status": "Abierto",
            "customer_id": normalized_customer_id,  # Organización de coincidencia de claves de fragmentación RUT
            "organization_rut": normalized_customer_id, # Persistir para requisitos de múltiples inquilinos
            "categoria": categoria,
            "prioridad": prioridad,
            "nivel_soporte_org": tier_contractual, # Almacenar el nivel contractual de la organización
            "tiempo_maximo_resolucion": sla_window,
            "fecha_expiracion_sla": fecha_expiracion_sla,
            "comentario_solucion": None,
            "justificacion_pausa": None,
            "en_proceso_at": None,
            "en_espera_at": None,
            "minutos_en_espera_acumulados": 0.0,
            "comentarios": [],
            "adjuntos": [],
            "__v": 0,                    # Versión OCC inicializada a 0
            "created_at": created_time
        }
        
        try:
            result = await collection.insert_one(document)
            document["_id"] = str(result.inserted_id)
            return document
        except DuplicateKeyError:
            raise AppError("Conflicto al guardar el ticket: el código generado ya existe.", status_code=409)

    @classmethod
    async def get_by_id(cls, ticket_id: str, organization_rut: str = None) -> dict:
        """Retrieve ticket by ID, with optional multi-tenant filtering."""
        collection = cls.get_collection()
        try:
            obj_id = ObjectId(ticket_id)
        except Exception:
            raise AppError("Formato de ID de ticket inválido.", status_code=400)
            
        query = {"_id": obj_id}
        if organization_rut:
            query["customer_id"] = organization_rut
            query["organization_rut"] = organization_rut

        doc = await collection.find_one(query)
        if doc:
            doc["_id"] = str(doc["_id"])
            if "organization_rut" not in doc:
                doc["organization_rut"] = doc["customer_id"]
        return doc

    @classmethod
    async def get_all(cls, organization_rut: str = None, search: str = None, prioridad: str = None, status: str = None, categoria: str = None, asignado_a: str = None) -> list:
        """Retrieve all tickets in MongoDB, with optional multi-tenant filtering, search, and dynamic status/priority/category/assignee filters using an explicit $and logical operator."""
        collection = cls.get_collection()
        query = {}
        
        base_filters = []
        if organization_rut:
            base_filters.append({"customer_id": organization_rut})
            base_filters.append({"organization_rut": organization_rut})

        if prioridad:
            base_filters.append({"prioridad": prioridad})

        if status:
            base_filters.append({"status": status})

        if categoria:
            base_filters.append({"categoria": categoria})

        if asignado_a:
            base_filters.append({"assigned_tech_id": asignado_a})

        if search:
            if organization_rut:
                # Límite de seguridad: búsqueda restringida estrictamente al título y código dentro del inquilino
                base_filters.append({
                    "$or": [
                        {"title": {"$regex": search, "$options": "i"}},
                        {"code": {"$regex": search, "$options": "i"}}
                    ]
                })
            else:
                base_filters.append({
                    "$or": [
                        {"title": {"$regex": search, "$options": "i"}},
                        {"code": {"$regex": search, "$options": "i"}},
                        {"description": {"$regex": search, "$options": "i"}}
                    ]
                })

        if base_filters:
            if len(base_filters) == 1:
                query = base_filters[0]
            else:
                query = {"$and": base_filters}

        cursor = collection.find(query)
        docs = await cursor.to_list(length=1000)
        for doc in docs:
            doc["_id"] = str(doc["_id"])
            if "organization_rut" not in doc:
                doc["organization_rut"] = doc["customer_id"]
        return docs

    @classmethod
    def validate_state_transition(cls, current_status: str, new_status: str):
        """
        RF-007 State Machine Transition Rules:
        - Initial: Abierto
        - Abierto -> Asignado (Only Asignado allowed from Abierto)
        - Asignado -> En Proceso (Cannot skip Asignado to go straight from Abierto to En Proceso!)
        - En Proceso -> En Espera (RF-010) or Resuelto
        - En Espera -> En Proceso (RF-007 transition back)
        - Resuelto -> Cerrado
        """
        if current_status == new_status:
            return

        transitions = {
            "Abierto": ["Asignado", "Cancelado"],
            "Asignado": ["En Proceso", "Cancelado"],
            "En Proceso": ["En Espera", "Resuelto", "Cancelado"],
            "En Espera": ["En Proceso", "Cancelado"],
            "Resuelto": ["Cerrado", "Cancelado"],
            "Cerrado": [],
            "Rechazado": [],
            "Cancelado": []
        }

        allowed_targets = transitions.get(current_status, [])
        if new_status not in allowed_targets:
            raise AppError(
                f"Transición ilegal: No se permite cambiar directamente del estado '{current_status}' "
                f"al estado '{new_status}'. El flujo mandatorio es: Abierto -> Asignado -> En Proceso -> (En Espera / Resuelto) -> Cerrado.",
                status_code=400
            )

    @classmethod
    async def update_status(cls, ticket_id: str, current_version: int, new_status: str, 
                            comentario_solucion: str = None, justificacion_pausa: str = None,
                            ip_origen: str = "127.0.0.1", organization_rut: str = None) -> dict:
        """
        Update the status of a ticket applying the transition state machine,
        Optimistic Concurrency Control (OCC), and custom fields mapping.
        """
        collection = cls.get_collection()
        try:
            obj_id = ObjectId(ticket_id)
        except Exception:
            raise AppError("Formato de ID de ticket inválido.", status_code=400)

        # 1. Obtenga el documento actual para validar las reglas de transición de estado
        fetch_query = {"_id": obj_id}
        if organization_rut:
            fetch_query["customer_id"] = organization_rut
            fetch_query["organization_rut"] = organization_rut

        current_ticket = await collection.find_one(fetch_query)
        if not current_ticket:
            raise AppError("El ticket no existe.", status_code=404)

        current_status = current_ticket.get("status", "Abierto")
        cls.validate_state_transition(current_status, new_status)

        now_time = datetime.now(timezone.utc)

        # 2. Cree cambios e incremente la carga útil.
        set_data = {
            "status": new_status
        }
        inc_data = {
            "__v": 1
        }
        
        # RF-007: ... transición a 'En Proceso'
        if new_status == "En Proceso":
            set_data["en_proceso_at"] = now_time
            
        # RF-008 y RF-010: Mapeo de entradas condicionales
        if new_status == "Resuelto":
            set_data["comentario_solucion"] = comentario_solucion
            set_data["resuelto_at"] = now_time
        elif new_status == "En Espera":
            set_data["justificacion_pausa"] = justificacion_pausa
            set_data["en_espera_at"] = now_time  # Guardar tiempo de inicio de espera

        # Transición DESDE En Espera: calcular minutos de espera transcurridos (corrección RF-015)
        if current_status == "En Espera":
            en_espera_start = current_ticket.get("en_espera_at")
            if en_espera_start:
                if en_espera_start.tzinfo is None:
                    en_espera_start = en_espera_start.replace(tzinfo=timezone.utc)
                paused_delta = now_time - en_espera_start
                paused_minutes = paused_delta.total_seconds() / 60
            else:
                paused_minutes = 0.0

            inc_data["minutos_en_espera_acumulados"] = paused_minutes
            set_data["en_espera_at"] = None

        # 3. Haga coincidir _id y la versión esperada (validación OCC)
        query = {
            "_id": obj_id,
            "__v": current_version
        }
        if organization_rut:
            query["customer_id"] = organization_rut
            query["organization_rut"] = organization_rut
        
        update_doc = {
            "$set": set_data,
            "$inc": inc_data
        }

        result = await collection.find_one_and_update(
            query,
            update_doc,
            return_document=ReturnDocument.AFTER
        )

        if result is None:
            # Compruebe si el documento existe (si existe, se trata de una colisión OCC)
            existing = await collection.find_one({"_id": obj_id})
            if not existing:
                raise AppError("El ticket no existe.", status_code=404)
            raise ConcurrencyError("Control de concurrencia: el ticket fue modificado por otro proceso simultáneamente. Reintente.")

        # RF-014: Registrador el cambio de estado en la bitácora forense inmutable
        await LogDAO.registrar_evento_forense(
            AuditLogDTO(
                id_ticket=result.get("code"),
                id_operador="sistema@techhelp.cl", # Placeholder, idealmente se pasaría el ID del usuario autenticado
                accion="Cambio de Estado",
                valor_anterior=current_status,
                nuevo_valor=new_status,
                ip_origen=ip_origen,
                ticket_id=ticket_id
            )
        )

        # Activador RF-022: generar token de encuesta y enviar correo electrónico cuando el ticket pase a Cerrado
        if new_status == "Cerrado":
            try:
                db = Database.get_db()
                org_doc = await db["organizations"].find_one({"rut": result.get("customer_id")})
                customer_email = org_doc.get("email", "cliente@desconocido.cl") if org_doc else "cliente@desconocido.cl"

                from backend.utils.token_generator import generate_survey_token
                token = await generate_survey_token(
                    ticket_id=ticket_id,
                    customer_email=customer_email,
                    tech_id=result.get("assigned_tech_id"),
                    tech_name=result.get("assigned_tech_name")
                )

                import asyncio
                from backend.utils.email_sender import send_survey_email
                asyncio.create_task(send_survey_email(customer_email, result.get("code"), token))
            except Exception as e:
                # Error de registro pero no falla la transición de actualización de estado
                logger.error(f"Error generando survey token al cerrar ticket: {str(e)}", exc_info=True)

        result["_id"] = str(result["_id"])
        return result

    @classmethod
    async def auto_assign(cls, ticket_id: str, current_version: int, ip_origen: str = "127.0.0.1") -> dict:
        """
        RF-013 Workload-based Auto-assignment (Corrections Phase):
        - Finds all technicians with status == 'Disponible' and whose especialidad matches the ticket's category.
        - Calculates active workload score based only on 'Asignado' and 'En Proceso' tickets (excluding 'En Espera').
        - Breaks ties by selecting the technician with the oldest 'ultima_asignacion_at' date.
        - Updates the chosen technician's 'ultima_asignacion_at' to the current UTC timestamp upon assignment.
        """
        db = Database.get_db()
        collection = cls.get_collection()

        try:
            obj_id = ObjectId(ticket_id)
        except Exception:
            raise AppError("Formato de ID de ticket inválido.", status_code=400)

        # 1. Recuperar el billete
        ticket = await collection.find_one({"_id": obj_id})
        if not ticket:
            raise AppError("El ticket no existe.", status_code=404)

        if ticket.get("status") != "Abierto":
            raise AppError("El ticket ya se encuentra asignado o en proceso.", status_code=400)

        category = ticket.get("categoria")

        # 2. Busque los técnicos disponibles cuya especialidad coincida con la categoría del ticket (filtro RF-013)
        available_techs = await db["technicians"].find({
            "status": "Disponible",
            "especialidad": category
        }).to_list(length=None)
        
        if not available_techs:
            # Mantener el ticket en estado Abierto
            return ticket

        # 3. Recupere todos los tickets activos para calcular la puntuación de la carga de trabajo.
        active_tickets = await collection.find({
            "status": {"$in": ["Asignado", "En Proceso"]}
        }).to_list(length=None)

        # 4. Seleccione el candidato con la puntuación de carga de trabajo más baja y la última fecha de asignación más antigua.
        from backend.utils.routing_algorithm import select_best_technician
        selected_tech = select_best_technician(available_techs, active_tickets)
        if not selected_tech:
            return ticket

        # 5. Realizar la asignación con el bloqueo OCC en el ticket
        query = {
            "_id": obj_id,
            "__v": current_version
        }

        update_doc = {
            "$set": {
                "status": "Asignado",
                "assigned_tech_id": str(selected_tech["_id"]),
                "assigned_tech_name": selected_tech["name"]
            },
            "$inc": {"__v": 1}
        }

        result = await collection.find_one_and_update(
            query,
            update_doc,
            return_document=ReturnDocument.AFTER
        )

        if result is None:
            raise ConcurrencyError("Control de concurrencia: el ticket fue modificado por otro proceso antes de la asignación.")

        # 6. Actualice la fecha de la última asignación del técnico elegida a la marca de tiempo UTC actual (actualización de desempate RF-013)
        await db["technicians"].update_one(
            {"_id": selected_tech["_id"]},
            {"$set": {"ultima_asignacion_at": datetime.now(timezone.utc)}}
        )

        # RF-014: Registrador la autoasignación en la bitácora forense
        await LogDAO.registrar_evento_forense(
            AuditLogDTO(
                id_ticket=result.get("code"),
                id_operador="sistema-autoasignacion@techhelp.cl",
                accion="Cambio de Estado",
                valor_anterior="Abierto",
                nuevo_valor="Asignado",
                ip_origen=ip_origen,
                ticket_id=ticket_id
            )
        )

        result["_id"] = str(result["_id"])
        return result

    @classmethod
    async def re_route(cls, ticket_id: str, current_version: int, motivo: str, nueva_categoria: str = None, ip_origen: str = "127.0.0.1") -> dict:
        """
        RF-011: Re-route, reject, or recategorize a ticket.
        If no category is provided, it goes to 'Rechazado' (frozen terminal state).
        If category is provided, it updates it, clears the assignee, and resets the SLA counters/state.
        """
        collection = cls.get_collection()
        try:
            obj_id = ObjectId(ticket_id)
        except Exception:
            raise AppError("Formato de ID de ticket inválido.", status_code=400)

        # 1. Obtenga el boleto actual para validar el estado y la versión.
        ticket = await collection.find_one({"_id": obj_id})
        if not ticket:
            raise AppError("El ticket no existe.", status_code=404)

        current_status = ticket.get("status")
        if current_status in ["Cerrado", "Rechazado"]:
            raise AppError(f"No se puede re-enrutar un ticket en estado '{current_status}'.", status_code=400)

        # 2. Conjunto de compilación y actualizaciones incluidas.
        set_data = {}
        inc_data = {"__v": 1}

        target_status = "Rechazado"
        if nueva_categoria and nueva_categoria.strip():
            target_status = "Abierto"
            set_data["categoria"] = nueva_categoria.strip()
            set_data["status"] = "Abierto"
            set_data["assigned_tech_id"] = None
            set_data["assigned_tech_name"] = None
            set_data["en_proceso_at"] = None
            set_data["en_espera_at"] = None
            set_data["minutos_en_espera_acumulados"] = 0.0
        else:
            set_data["status"] = "Rechazado"

        # 3. Agregue el motivo del motivo como comentario interno.
        comment_obj = {
            "texto": f"Re-enrutamiento/Rechazo: {motivo}",
            "es_interno": True,
            "autor": "sistema@techhelp.cl",
            "rol_autor": "Sistema",
            "timestamp": datetime.now(timezone.utc)
        }

        query = {
            "_id": obj_id,
            "__v": current_version
        }

        update_doc = {
            "$set": set_data,
            "$inc": inc_data,
            "$push": {"comentarios": comment_obj}
        }

        result = await collection.find_one_and_update(
            query,
            update_doc,
            return_document=ReturnDocument.AFTER
        )

        if result is None:
            existing = await collection.find_one({"_id": obj_id})
            if not existing:
                raise AppError("El ticket no existe.", status_code=404)
            raise ConcurrencyError("Control de concurrencia: el ticket fue modificado por otro proceso simultáneamente.")

        # RF-014: Registrador el re-enrutamiento/rechazo en la bitácora forense
        await LogDAO.registrar_evento_forense(
            AuditLogDTO(
                id_ticket=result.get("code"),
                id_operador="sistema@techhelp.cl", # Marcador de posición
                accion="Re-enrutamiento/Rechazo",
                valor_anterior=current_status,
                nuevo_valor=target_status,
                ip_origen=ip_origen,
                ticket_id=ticket_id
            )
        )

        result["_id"] = str(result["_id"])
        return result

    @classmethod
    async def update_priority(cls, ticket_id: str, current_version: int, nueva_prioridad: str, 
                              justificacion: str, ip_origen: str = "127.0.0.1") -> dict:
        """
        RF-016: Reclassify ticket priority and recalculate SLA deadline.
        The new deadline is calculated from the current UTC timestamp (now) to avoid retroactive breaches.
        """
        collection = cls.get_collection()
        try:
            obj_id = ObjectId(ticket_id)
        except Exception:
            raise AppError("Formato de ID de ticket inválido.", status_code=400)

        # 1. Obtener el documento actual
        ticket = await collection.find_one({"_id": obj_id})
        if not ticket:
            raise AppError("El ticket no existe.", status_code=404)

        current_priority = ticket.get("prioridad")
        current_status = ticket.get("status")
        if current_status in ["Cerrado", "Rechazado"]:
            raise AppError(f"No se puede reclasificar la prioridad de un ticket en estado '{current_status}'.", status_code=400)

        # 2. Obtenga el nivel de soporte del billete
        nivel_soporte = ticket.get("nivel_soporte_org", "Bronce")

        # 3. Vuelva a calcular la nueva ventana del SLA según la nueva prioridad y nivel
        from backend.utils.sla_matrix import get_sla_window
        from datetime import timedelta
        sla_window = get_sla_window(nivel_soporte, nueva_prioridad)
        now_time = datetime.now(timezone.utc)
        nueva_expiracion = now_time + timedelta(minutes=sla_window)

        # 4. Insertar comentario de justificación.
        comment_obj = {
            "texto": f"Reclasificación de Prioridad a {nueva_prioridad}. Justificación: {justificacion}",
            "es_interno": True,
            "autor": "sistema@techhelp.cl",
            "rol_autor": "Sistema",
            "timestamp": now_time
        }

        # 5. Actualización de verificación de versión de OCC
        query = {
            "_id": obj_id,
            "__v": current_version
        }

        update_doc = {
            "$set": {
                "prioridad": nueva_prioridad,
                "tiempo_maximo_resolucion": sla_window,
                "fecha_expiracion_sla": nueva_expiracion
            },
            "$inc": {"__v": 1},
            "$push": {"comentarios": comment_obj}
        }

        result = await collection.find_one_and_update(
            query,
            update_doc,
            return_document=ReturnDocument.AFTER
        )

        if result is None:
            existing = await collection.find_one({"_id": obj_id})
            if not existing:
                raise AppError("El ticket no existe.", status_code=404)
            raise ConcurrencyError("Control de concurrencia: el ticket fue modificado por otro proceso simultáneamente.")

        # RF-014: Registrador la reclasificación de prioridad en la bitácora forense
        await LogDAO.registrar_evento_forense(
            AuditLogDTO(
                id_ticket=result.get("code"),
                id_operador="sistema@techhelp.cl", # Marcador de posición
                accion="Reclasificación de Prioridad",
                valor_anterior=current_priority,
                nuevo_valor=nueva_prioridad,
                ip_origen=ip_origen,
                ticket_id=ticket_id
            )
        )

        result["_id"] = str(result["_id"])
        return result

    @classmethod
    async def add_attachment(cls, ticket_id: str, url: str) -> dict:
        """
        RF-006: Associate attachment URL string in the 'adjuntos' array in the ticket document.
        """
        collection = cls.get_collection()
        try:
            obj_id = ObjectId(ticket_id)
        except Exception:
            raise AppError("Formato de ID de ticket inválido.", status_code=400)
        
        # Consulta estado actual para bloquear tickets cerrados/rechazados (RF-009)
        ticket = await collection.find_one({"_id": obj_id})
        if not ticket:
            raise AppError("El ticket no existe.", status_code=404)
        if ticket.get("status") in ["Cerrado", "Rechazado"]:
            raise AppError(f"No se pueden subir adjuntos a un ticket en estado '{ticket.get('status')}'.", status_code=400)

        result = await collection.find_one_and_update(
            {"_id": obj_id},
            {"$push": {"adjuntos": url}, "$inc": {"__v": 1}},
            return_document=ReturnDocument.AFTER
        )
        if result is None:
            raise AppError("El ticket no existe.", status_code=404)
        
        result["_id"] = str(result["_id"])
        return result

    @classmethod
    async def add_comment(cls, ticket_id: str, comment_text: str, es_interno: bool, 
                          author_email: str, author_role: str, author_name: str = "Usuario") -> dict:
        """
        RF-017 & RF-018: Add a comment dictionary object inside the 'comentarios' array in the ticket document with enriched user identity.
        """
        collection = cls.get_collection()
        try:
            obj_id = ObjectId(ticket_id)
        except Exception:
            raise AppError("Formato de ID de ticket inválido.", status_code=400)
            
        # Verifique el estado actual para bloquear boletos cerrados/rechazados/cancelados
        ticket = await collection.find_one({"_id": obj_id})
        if not ticket:
            raise AppError("El ticket no existe.", status_code=404)
        if ticket.get("status") in ["Cerrado", "Rechazado", "Cancelado"]:
            raise AppError("No se pueden añadir comentarios a un ticket finalizado", status_code=400)

        comment_obj = {
            "texto": comment_text,
            "es_interno": es_interno,
            "autor": author_email,
            "rol_autor": author_role,
            "autor_nombre": author_name,
            "autor_email": author_email,
            "autor_rol": author_role,
            "timestamp": datetime.now(timezone.utc)
        }
        
        result = await collection.find_one_and_update(
            {"_id": obj_id},
            {"$push": {"comentarios": comment_obj}, "$inc": {"__v": 1}},
            return_document=ReturnDocument.AFTER
        )
        if result is None:
            raise AppError("El ticket no existe.", status_code=404)
            
        result["_id"] = str(result["_id"])
        return result

    @classmethod
    async def submit_direct_feedback(cls, ticket_id: str, client_email: str, valoracion: int, comentarios: str = None) -> dict:
        """
        Submite retroalimentación directa para un ticket cerrado.
        """
        db = Database.get_db()
        collection = cls.get_collection()
        
        try:
            obj_id = ObjectId(ticket_id)
        except Exception:
            raise AppError("Formato de ID de ticket inválido.", status_code=400)
            
        ticket = await collection.find_one({"_id": obj_id})
        if not ticket:
            raise AppError("El ticket no existe.", status_code=404)
            
        # Verificar que la organización pertenece al correo electrónico del cliente
        org_doc = await db["organizations"].find_one({"email": client_email})
        if not org_doc:
            raise AppError("Organización cliente no encontrada.", status_code=404)
            
        client_rut = org_doc.get("rut")
        if ticket.get("customer_id") != client_rut:
            raise AppError("El ticket no pertenece a la organización del cliente.", status_code=403)
            
        if ticket.get("status") != "Cerrado":
            raise AppError("El ticket debe estar en estado Cerrado para registrar una reseña.", status_code=400)
            
        # Comprobar si ya se revisó
        existing = await db["satisfaccion_cliente"].find_one({"ticket_id": ticket_id})
        if existing:
            raise AppError("Esta encuesta ya fue respondida.", status_code=400)
            
        feedback_doc = {
            "ticket_id": ticket_id,
            "customer_email": client_email,
            "valoracion": valoracion,
            "comentarios": comentarios,
            "tech_id": ticket.get("assigned_tech_id"),
            "tech_name": ticket.get("assigned_tech_name"),
            "created_at": datetime.now(timezone.utc)
        }
        
        await db["satisfaccion_cliente"].insert_one(feedback_doc)
        return feedback_doc