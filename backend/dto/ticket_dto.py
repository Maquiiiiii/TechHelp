from datetime import datetime, timezone
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from backend.dto.organization_dto import validate_chilean_rut

# Prioridades permitidas
PriorityType = Literal["Baja", "Media", "Alta", "Crítica"]

# Estados permitidos
StatusType = Literal["Abierto", "Asignado", "En Proceso", "En Espera", "Resuelto", "Cerrado", "Rechazado", "Cancelado"]


class TicketCreateDTO(BaseModel):
    title: str = Field(..., min_length=3, max_length=150, json_schema_extra={"example": "Error al conectar base de datos"})
    description: str = Field(..., min_length=20, json_schema_extra={"example": "La base de datos del servidor central de reportes arroja timeout persistente de 30 segundos al intentar iniciar la sesión."})
    customer_id: str = Field(..., description="RUT de la organización (ej: 12.345.678-9)")
    organization_rut: Optional[str] = Field(None, description="RUT de la organización (ej: 12.345.678-9)")
    categoria: str = Field(..., json_schema_extra={"example": "Bases de Datos"})
    prioridad: PriorityType = Field(..., description="Prioridad del ticket (Baja, Media, Alta, Crítica)")

    @field_validator("customer_id")
    @classmethod
    def validate_customer_id(cls, v: str) -> str:
        # Valide customer_id utilizando la lógica RUT chilena del Módulo 11 para garantizar la compatibilidad del diseño de fragmentación
        return validate_chilean_rut(v)

    @field_validator("organization_rut")
    @classmethod
    def validate_org_rut(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return validate_chilean_rut(v)
        return v

class TicketStatusUpdateDTO(BaseModel):
    status: StatusType = Field(..., description="Nuevo estado del ticket")
    version: int = Field(..., alias="version", description="Versión actual (__v) del ticket para control de concurrencia (OCC)")
    comentario_solucion: Optional[str] = Field(None, description="Mensaje obligatorio cuando el estado cambia a 'Resuelto'")
    justificacion_pausa: Optional[str] = Field(None, description="Mensaje obligatorio cuando el estado cambia a 'En Espera'")

    @model_validator(mode="after")
    def check_conditional_inputs(self) -> "TicketStatusUpdateDTO":
        """Enforces conditional validation depending on the target status."""
        status_val = self.status
        
        if status_val == "Resuelto":
            if not self.comentario_solucion or not self.comentario_solucion.strip():
                raise ValueError("El campo 'comentario_solucion' es obligatorio cuando el estado es 'Resuelto' (RF-008).")
                
        elif status_val == "En Espera":
            if not self.justificacion_pausa or not self.justificacion_pausa.strip():
                raise ValueError("El campo 'justificacion_pausa' es obligatorio cuando el estado es 'En Espera' (RF-010).")
                
        return self

class TicketResponseDTO(BaseModel):
    id: str = Field(..., alias="_id")
    code: str = Field(..., pattern=r"^TK-\d{5}$")
    title: str

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        import re
        if not re.match(r"^TK-[0-9]{5}$", v):
            raise ValueError("El código del ticket debe cumplir con el patrón regex ^TK-[0-9]{5}$")
        return v
    description: str
    status: str
    customer_id: str
    organization_rut: Optional[str] = None
    categoria: str
    prioridad: str
    comentario_solucion: Optional[str] = None
    justificacion_pausa: Optional[str] = None
    tiempo_maximo_resolucion: Optional[int] = None
    fecha_expiracion_sla: Optional[datetime] = None
    assigned_tech_id: Optional[str] = None
    assigned_tech_name: Optional[str] = None
    en_proceso_at: Optional[datetime] = None
    comentarios: Optional[list[dict]] = None
    adjuntos: Optional[list[str]] = None
    created_at: datetime
    v: int = Field(..., alias="__v")
    feedback_submitted: Optional[bool] = None

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        json_schema_extra = {
            "example": {
                "_id": "60d5ec49f1a2c529a8a7c2f5",
                "code": "TK-12345",
                "title": "Error al conectar base de datos",
                "description": "La base de datos del servidor central de reportes arroja timeout...",
                "status": "Abierto",
                "customer_id": "12345678-5",
                "categoria": "Bases de Datos",
                "prioridad": "Alta",
                "__v": 0,
                "created_at": "2026-07-04T03:52:00Z"
            }
        }

class TicketReRouteDTO(BaseModel):
    motivo: str = Field(..., min_length=15, description="Motivo obligatorio del rechazo o cambio de ruta (mínimo 15 caracteres)")
    nueva_categoria: Optional[str] = Field(None, description="Nueva categoría opcional si se desea recategorizar y re-enrutar el ticket")
    version: int = Field(..., alias="version", description="Versión actual (__v) del ticket para control de concurrencia (OCC)")

    class Config:
        populate_by_name = True

class TicketPriorityUpdateDTO(BaseModel):
    prioridad: PriorityType = Field(..., description="Nueva prioridad del ticket (Baja, Media, Alta, Crítica)")
    justificacion: str = Field(..., min_length=10, description="Justificación obligatoria para la reclasificación (mínimo 10 caracteres)")
    version: int = Field(..., alias="version", description="Versión actual (__v) del ticket para control de concurrencia (OCC)")

    class Config:
        populate_by_name = True


class AuditLogDTO(BaseModel): # RF-014 y RNF-SEG-004
    id_ticket: str = Field(..., pattern=r"^TK-[0-9]{5}$", description="Código del ticket afectado en formato TK-XXXXX.")
    id_operador: str = Field(..., description="ID o email del usuario/sistema que ejecuta la acción.")
    accion: str = Field(..., description="Descripción de la acción realizada (ej: 'Cambio de Estado', 'Reclasificación de Prioridad').")

    @field_validator("id_ticket")
    @classmethod
    def validate_id_ticket(cls, v: str) -> str:
        import re
        if not re.match(r"^TK-[0-9]{5}$", v):
            raise ValueError("El código del ticket debe cumplir con el patrón regex ^TK-[0-9]{5}$")
        return v
    valor_anterior: Optional[str] = Field(..., description="Valor de la propiedad antes de la mutación.")
    nuevo_valor: Optional[str] = Field(..., description="Valor de la propiedad después de la mutación.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp en UTC con precisión de milisegundos, capturado automáticamente.")
    ip_origen: str = Field(..., description="Dirección IP de origen de la solicitud.")
    ticket_id: Optional[str] = Field(default=None, description="Legacy MongoDB ID string reference for backward compatibility")

    class Config:
        json_schema_extra = {
            "example": {
                "id_ticket": "TK-12345",
                "id_operador": "admin@techhelp.cl",
                "accion": "Cambio de Estado",
                "valor_anterior": "Abierto",
                "nuevo_valor": "Asignado",
                "ip_origen": "192.168.1.100"
            }
        }