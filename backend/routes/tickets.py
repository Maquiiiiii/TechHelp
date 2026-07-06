import logging
from fastapi import APIRouter, status, Path, Request, UploadFile, File, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from backend.dto.ticket_dto import TicketCreateDTO, TicketStatusUpdateDTO, TicketResponseDTO, TicketReRouteDTO, TicketPriorityUpdateDTO
from backend.dao.ticket_dao import TicketDAO
from backend.security.auth import get_current_user, RoleChecker



logger = logging.getLogger("techhelp.routes.tickets")

router = APIRouter(
    prefix="/tickets",
    tags=["Tickets"]
)

class CommentCreateDTO(BaseModel):
    texto: str = Field(..., min_length=1, description="Contenido de la nota o comentario")
    es_interno: bool = Field(default=False, description="Si es True, la nota es interna y oculta para los Clientes")

async def get_client_rut(current_user: dict) -> str:
    # Primero verifique si la carga útil del token tiene organización_rut o rutina
    rut = current_user.get("organization_rut") or current_user.get("rut")
    if not rut:
        # Alternativa para consultar la colección de la organización utilizando el correo electrónico del cliente (sub)
        email = current_user.get("sub")
        if email:
            from backend.config.database import Database
            db = Database.get_db()
            org = await db["organizations"].find_one({"email": email})
            if org:
                rut = org.get("rut")
    return rut

@router.post(
    "",
    response_model=TicketResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un Ticket de Soporte (RF-005)",
    description="Crea un nuevo ticket de soporte asociado a una organización cliente existente."
)
async def create_ticket(
    request: Request,
    payload: TicketCreateDTO,
    current_user: dict = Depends(get_current_user)
):
    role = current_user.get("role") or current_user.get("rol")
    if role == "Cliente":
        # Verifique si el cliente intentó pasar los campos de técnico/asignación
        body_json = {}
        try:
            body_json = await request.json()
        except Exception:
            pass
        if "technician_id" in body_json or "assigned_to" in body_json or "assigned_tech_id" in body_json or "assigned_tech_name" in body_json:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: los clientes no pueden asignar técnicos ni modificar campos de asignación."
            )
        
        client_rut = await get_client_rut(current_user)
        if not client_rut:
            raise HTTPException(status_code=403, detail="No se pudo determinar el RUT del cliente.")
        
        # Crítico para la seguridad: ignore cualquier RUT enviado en el cuerpo por el cliente e inyecte RUT verificado
        payload.customer_id = client_rut
        payload.organization_rut = client_rut

    new_ticket = await TicketDAO.create(
        title=payload.title,
        description=payload.description,
        customer_id=payload.customer_id,
        categoria=payload.categoria,
        prioridad=payload.prioridad
    )
    logger.info(f"Ticket creado con éxito: Código {new_ticket['code']} para cliente {payload.customer_id}")
    return new_ticket

@router.get(
    "",
    response_model=list[TicketResponseDTO],
    status_code=status.HTTP_200_OK,
    summary="Listar todos los tickets",
    description="Retorna el listado completo de tickets."
)
async def list_tickets(
    search: Optional[str] = None,
    prioridad: Optional[str] = None,
    status: Optional[str] = None,
    categoria: Optional[str] = None,
    asignado_a: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    role = current_user.get("role") or current_user.get("rol")
    organization_rut = None
    if role == "Cliente":
        organization_rut = await get_client_rut(current_user)
        if not organization_rut:
            raise HTTPException(status_code=403, detail="No se pudo determinar el RUT del cliente.")
            
    if role == "Tecnico" and asignado_a:
        from backend.config.database import Database
        db = Database.get_db()
        tech = await db["technicians"].find_one({"email": current_user.get("sub")})
        if tech:
            asignado_a = str(tech["_id"])

    tickets = await TicketDAO.get_all(
        organization_rut=organization_rut,
        search=search,
        prioridad=prioridad,
        status=status,
        categoria=categoria,
        asignado_a=asignado_a
    )
    if role == "Cliente":
        for ticket in tickets:
            if "comentarios" in ticket and ticket["comentarios"]:
                ticket["comentarios"] = [c for c in ticket["comentarios"] if not c.get("es_interno", False)]
    return tickets

@router.get(
    "/{ticket_id}",
    response_model=TicketResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Obtener Detalle del Ticket (RF-017)",
    description="Retorna el detalle de un ticket. Si el usuario logueado posee el rol 'Cliente', "
                "se excluyen absolutamente todos los comentarios internos (es_interno = True) del listado."
)
async def get_ticket(
    ticket_id: str = Path(..., description="ID del ticket en MongoDB"),
    current_user: dict = Depends(get_current_user)
):
    role = current_user.get("role")
    organization_rut = None
    if role == "Cliente":
        organization_rut = await get_client_rut(current_user)
        if not organization_rut:
            raise HTTPException(status_code=403, detail="No se pudo determinar el RUT del cliente.")

    ticket = await TicketDAO.get_by_id(ticket_id, organization_rut=organization_rut)
    if not ticket:
        raise HTTPException(status_code=404, detail="El ticket no existe o pertenece a otra organización.")

    # RF-017 Criterio de Aceptación: Excluir comentarios internos si el rol es Cliente
    if role == "Cliente" and "comentarios" in ticket and ticket["comentarios"]:
        ticket["comentarios"] = [c for c in ticket["comentarios"] if not c.get("es_interno", False)]

    # Compruebe si los comentarios ya se enviaron
    from backend.config.database import Database
    db = Database.get_db()
    feedback = await db["satisfaccion_cliente"].find_one({"ticket_id": ticket_id})
    ticket["feedback_submitted"] = feedback is not None

    return ticket

@router.put(
    "/{ticket_id}/status",
    response_model=TicketResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Actualizar Estado del Ticket (RF-007, RF-010, RNF-ESC-003)",
    description="Actualiza el estado de un ticket aplicando la máquina de estados obligatoria y registrando la IP de origen."
)
async def update_ticket_status(
    request: Request,
    ticket_id: str = Path(..., description="ID hexadecimal del ticket en MongoDB"),
    payload: TicketStatusUpdateDTO = ...,
    current_user: dict = Depends(get_current_user)
):
    role = current_user.get("role")
    organization_rut = None
    if role == "Cliente":
        # Verifique si el cliente intentó pasar los campos de técnico/asignación
        body_json = {}
        try:
            body_json = await request.json()
        except Exception:
            pass
        if "technician_id" in body_json or "assigned_to" in body_json or "assigned_tech_id" in body_json or "assigned_tech_name" in body_json:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: los clientes no pueden asignar técnicos ni modificar campos de asignación."
            )
            
        # Los clientes solo pueden establecer el estado en Cancelado o Resuelto
        if payload.status not in ["Cancelado", "Resuelto"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Acceso denegado: los clientes solo pueden cambiar el estado a 'Cancelado' o 'Resuelto', no a '{payload.status}'."
            )
            
        organization_rut = await get_client_rut(current_user)
        if not organization_rut:
            raise HTTPException(status_code=403, detail="No se pudo determinar el RUT del cliente.")

    ip_origen = request.client.host if request.client else "127.0.0.1"
    updated_ticket = await TicketDAO.update_status(
        ticket_id=ticket_id,
        current_version=payload.version,
        new_status=payload.status,
        comentario_solucion=payload.comentario_solucion,
        justificacion_pausa=payload.justificacion_pausa,
        ip_origen=ip_origen,
        organization_rut=organization_rut
    )
    logger.info(f"Estado del ticket {ticket_id} actualizado exitosamente a '{payload.status}' por IP {ip_origen}")
    return updated_ticket

class TicketAutoAssignDTO(BaseModel):
    version: int = Field(..., description="Versión actual (__v) para el control de concurrencia optimista")

@router.post(
    "/{ticket_id}/auto-assign",
    response_model=TicketResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Autoasignación Ponderada de Técnico (RF-013)",
    description="Asigna automáticamente el ticket abierto al técnico disponible con menor carga de trabajo activa ponderada."
)
async def auto_assign_ticket(
    request: Request,
    ticket_id: str = Path(..., description="ID del ticket en MongoDB"),
    payload: TicketAutoAssignDTO = ...,
    current_user: dict = Depends(get_current_user)
):
    role = current_user.get("role")
    if role == "Cliente":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: los clientes no están autorizados para autoasignar técnicos."
        )
    ip_origen = request.client.host if request.client else "127.0.0.1"
    assigned_ticket = await TicketDAO.auto_assign(
        ticket_id=ticket_id,
        current_version=payload.version,
        ip_origen=ip_origen
    )
    return assigned_ticket

@router.post(
    "/{ticket_id}/attachments",
    response_model=TicketResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Adjuntar Archivo a Ticket (RF-006)",
    description="Permite subir un archivo asociado al ticket. Valida tamaño (< 5MB) y extensiones (PDF, PNG, JPG)."
)
async def upload_attachment(
    ticket_id: str = Path(..., description="ID del ticket en MongoDB"),
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    role = current_user.get("role")
    if role == "Cliente":
        client_rut = await get_client_rut(current_user)
        ticket = await TicketDAO.get_by_id(ticket_id)
        if not ticket or ticket.get("customer_id") != client_rut:
            raise HTTPException(status_code=403, detail="Acceso denegado: el ticket pertenece a otra organización.")

    # 1. Validar la extensión del archivo (PDF, PNG, JPG/JPEG)
    filename = file.filename
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    if ext not in ["pdf", "png", "jpg", "jpeg"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Formato de archivo no permitido. Solo se aceptan PDF, PNG y JPG."
        )

    # 2. Validar el tamaño del archivo (límite de 5 MB)
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="El archivo excede el tamaño máximo permitido de 5MB."
        )

    # 3. Guarde el archivo físico localmente
    import os
    import uuid
    UPLOAD_DIR = "uploads"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    unique_filename = f"{uuid.uuid4().hex}_{filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    with open(file_path, "wb") as f:
        f.write(contents)
        
    local_url = f"http://localhost:8000/uploads/{unique_filename}"

    # 4. Conservar la cadena de URL del archivo adjunto en la matriz
    updated_ticket = await TicketDAO.add_attachment(ticket_id, local_url)
    logger.info(f"Archivo {filename} adjuntado exitosamente de forma local en ticket {ticket_id}.")
    return updated_ticket

@router.post(
    "/{ticket_id}/comments",
    response_model=TicketResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Agregar Nota o Comentario a Ticket (RF-017, RF-018)",
    description="Permite a los usuarios registrados comentar un ticket, controlando la visibilidad interna."
)
async def add_comment_to_ticket(
    ticket_id: str = Path(..., description="ID del ticket en MongoDB"),
    payload: CommentCreateDTO = ...,
    current_user: dict = Depends(get_current_user)
):
    author_email = current_user.get("sub", "desconocido")
    author_role = current_user.get("role") or current_user.get("rol") or "Cliente"

    # Obtenga un ticket para comprobar la existencia, el acceso multiinquilino y el estado.
    ticket = await TicketDAO.get_by_id(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")

    # Comprueba si la organización está activa.
    from backend.config.database import Database
    db = Database.get_db()
    org = await db["organizations"].find_one({"rut": ticket.get("customer_id")})
    if org and org.get("activo", True) is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pueden añadir comentarios a un ticket de una organización desactivada"
        )

    if author_role == "Cliente":
        client_rut = await get_client_rut(current_user)
        if ticket.get("customer_id") != client_rut:
            raise HTTPException(status_code=403, detail="Acceso denegado: el ticket pertenece a otra organización.")

    if ticket.get("status") in ["Cerrado", "Rechazado", "Cancelado"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pueden añadir comentarios a un ticket finalizado"
        )

    # Resolver nombre completo del autor
    author_name = current_user.get("name")
    if not author_name:
        from backend.config.database import Database
        db = Database.get_db()
        if author_role == "Cliente":
            client_rut = await get_client_rut(current_user)
            org = await db["organizations"].find_one({"rut": client_rut})
            author_name = org.get("name") if org else "Cliente TechHelp"
        elif author_role == "Tecnico":
            tech = await db["technicians"].find_one({"email": author_email})
            author_name = tech.get("name") if tech else "Técnico TechHelp"
        else:
            author_name = "Admin"

    # 1. Persistir comentario dentro de la base de datos.
    updated_ticket = await TicketDAO.add_comment(
        ticket_id=ticket_id,
        comment_text=payload.texto,
        es_interno=payload.es_interno,
        author_email=author_email,
        author_role=author_role,
        author_name=author_name
    )

    # 2. RF-018: Enviar correo electrónico de alerta simulado si el comentario es público y el autor es un técnico
    if not payload.es_interno and author_role == "Tecnico":
        alert_msg = f"Enviando email de alerta al cliente con URL: /tickets/{ticket_id}"
        print(alert_msg)
        logger.warning(alert_msg)
        try:
            from backend.config.database import Database
            db = Database.get_db()
            org_doc = await db["organizations"].find_one({"rut": updated_ticket.get("customer_id")})
            customer_email = org_doc.get("email") if org_doc else None
            if customer_email:
                import asyncio
                from backend.utils.email_sender import send_comment_notification_email
                asyncio.create_task(
                    send_comment_notification_email(
                        email=customer_email,
                        ticket_code=updated_ticket.get("code"),
                        ticket_id=ticket_id
                    )
                )
        except Exception as e:
            logger.error(f"Error dispatching comment notification email: {str(e)}")

    return updated_ticket

@router.put(
    "/{ticket_id}/re-route",
    response_model=TicketResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Devolución, Rechazo y Recategorización de Ticket (RF-011)",
    description="Permite a Técnicos y Administradores re-enrutar, rechazar o recategorizar un ticket. "
                "Si no se incluye 'nueva_categoria', el ticket pasa permanentemente a 'Rechazado'. "
                "Si se incluye 'nueva_categoria', se actualiza la categoría y se reinician los contadores y estados de SLA.",
    dependencies=[Depends(RoleChecker(["Tecnico", "Administrador"]))]
)
async def re_route_ticket(
    request: Request,
    ticket_id: str = Path(..., description="ID del ticket en MongoDB"),
    payload: TicketReRouteDTO = ...,
):
    ip_origen = request.client.host if request.client else "127.0.0.1"
    updated = await TicketDAO.re_route(
        ticket_id=ticket_id,
        current_version=payload.version,
        motivo=payload.motivo,
        nueva_categoria=payload.nueva_categoria,
        ip_origen=ip_origen
    )
    logger.info(f"Re-enrutamiento procesado para ticket {ticket_id}. Categoría nueva: {payload.nueva_categoria}, IP: {ip_origen}")
    return updated

@router.put(
    "/{ticket_id}/priority",
    response_model=TicketResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Reclasificación de Prioridad de Ticket (RF-016)",
    description="Permite a los Administradores modificar la prioridad de un ticket y recalcular de inmediato "
                "la fecha de expiración del SLA a partir del momento del cambio, para evitar vencimientos retroactivos.",
    dependencies=[Depends(RoleChecker(["Administrador"]))]
)
async def update_ticket_priority(
    request: Request,
    ticket_id: str = Path(..., description="ID del ticket en MongoDB"),
    payload: TicketPriorityUpdateDTO = ...,
):
    ip_origen = request.client.host if request.client else "127.0.0.1"
    updated = await TicketDAO.update_priority(
        ticket_id=ticket_id,
        current_version=payload.version,
        nueva_prioridad=payload.prioridad,
        justificacion=payload.justificacion,
        ip_origen=ip_origen
    )
    logger.info(f"Prioridad del ticket {ticket_id} actualizada a {payload.prioridad} por Administrador. IP: {ip_origen}")
    return updated
from pydantic import field_validator

class FeedbackDirectDTO(BaseModel):
    valoracion: int = Field(..., ge=1, le=5, description="Valoración entera de estrellas [1, 5]")
    comentarios: Optional[str] = Field(None, description="Comentarios opcionales del cliente")

    @field_validator("valoracion")
    @classmethod
    def validate_valoracion(cls, v: int) -> int:
        if not isinstance(v, int):
            raise ValueError("La valoración de estrellas debe ser estrictamente un número entero.")
        if v < 1 or v > 5:
            raise ValueError("La valoración debe estar en el rango de 1 a 5 estrellas.")
        return v

@router.post(
    "/{ticket_id}/feedback",
    status_code=status.HTTP_201_CREATED,
    summary="Registrar Retroalimentación Directa del Cliente (RF-023)",
    description="Permite al cliente calificar un ticket cerrado directamente desde el detalle."
)
async def submit_direct_feedback(
    ticket_id: str = Path(..., description="ID del ticket en MongoDB"),
    payload: FeedbackDirectDTO = ...,
    current_user: dict = Depends(get_current_user)
):
    role = current_user.get("role")
    if role != "Cliente":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: solo los clientes pueden registrar retroalimentación"
        )
    
    email = current_user.get("sub")
    feedback = await TicketDAO.submit_direct_feedback(
        ticket_id=ticket_id,
        client_email=email,
        valoracion=payload.valoracion,
        comentarios=payload.comentarios
    )
    return {"message": "Reseña registrada con éxito", "feedback_id": str(feedback["_id"])}