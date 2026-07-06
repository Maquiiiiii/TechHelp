import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, status, HTTPException
from pydantic import BaseModel, Field
from backend.security.auth import hash_password, verify_password, create_access_token, decode_access_token

logger = logging.getLogger("techhelp.routes.login")

router = APIRouter(
    prefix="/login",
    tags=["Authentication"]
)

# Hash de administrador predefinido (contraseña: "admin123")
ADMIN_EMAIL = "admin@techhelp.cl"
ADMIN_PASSWORD_HASH = hash_password("admin123")

# Seguimiento en memoria de intentos fallidos y tiempos de bloqueo
ADMIN_STATE = {
    ADMIN_EMAIL: {
        "failed_attempts": 0,
        "locked_until": None
    }
}

from pydantic import model_validator
from typing import Optional

class LoginStep1DTO(BaseModel):
    identifier: Optional[str] = Field(None, example="admin@techhelp.cl")
    email: Optional[str] = Field(None, example="admin@techhelp.cl")
    password: str = Field(..., example="admin123")

    @model_validator(mode="after")
    def validate_identifier(self):
        if not self.identifier and not self.email:
            raise ValueError("Debe proporcionar un identificador o email.")
        if not self.identifier:
            self.identifier = self.email
        return self

class LoginStep2DTO(BaseModel):
    temp_token: str = Field(..., description="Token temporal de MFA devuelto en el Paso 1")
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$", example="123456")

@router.post(
    "/step1",
    status_code=status.HTTP_200_OK,
    summary="Login Paso 1: Validación de Credenciales (RF-021)",
    description="Valida el correo o RUT y la contraseña. "
                "Si son correctos, inicia sesión o devuelve token temporal de MFA."
)
async def login_step1(payload: LoginStep1DTO):
    identifier = payload.identifier
    password = payload.password

    from backend.dto.organization_dto import validate_chilean_rut
    try:
        normalized_identifier = validate_chilean_rut(identifier)
    except Exception:
        normalized_identifier = identifier

    # Comprobar si la cuenta está actualmente bloqueada
    state = ADMIN_STATE.setdefault(identifier, {"failed_attempts": 0, "locked_until": None})
    if state["locked_until"] and datetime.now(timezone.utc) < state["locked_until"]:
        delta = state["locked_until"] - datetime.now(timezone.utc)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cuenta bloqueada temporalmente por excesivos intentos fallidos de OTP. Intente en {int(delta.total_seconds())} segundos."
        )

    # 1. Flujo de inicio de sesión del administrador
    if identifier == ADMIN_EMAIL or identifier == "admin":
        if not verify_password(password, ADMIN_PASSWORD_HASH):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
        
        # Genera un token temporal para la verificación OTP del paso 2
        temp_token = create_access_token(
            data={"sub": ADMIN_EMAIL, "role": "Administrador", "mfa_pending": True},
            expires_delta=timedelta(minutes=5)
        )
        logger.info(f"Paso 1 de Login correcto para {ADMIN_EMAIL}. MFA requerido.")
        return {"mfa_required": True, "temp_token": temp_token}

    # 2. Flujo de inicio de sesión del cliente (organización)
    from backend.dao.organization_dao import OrganizationDAO
    org = await OrganizationDAO.get_collection().find_one({
        "$or": [
            {"email": identifier},
            {"rut": normalized_identifier}
        ]
    })
    if org:
        if org.get("activo", True) is False:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cuenta bloqueada: su organización ha sido desactivada."
            )
        # Admitir cliente predeterminado 123 o RUT de organización como contraseña para fines de demostración
        if password in ["client123", org["rut"], "password123"]:
            access_token = create_access_token(
                data={
                    "sub": org["email"], 
                    "role": "Cliente", 
                    "organization_rut": org["rut"], 
                    "name": org["name"],
                    "cuenta_bloqueada": False
                },
                expires_delta=timedelta(minutes=60)
            )
            logger.info(f"Login exitoso directo para Cliente {org['email']} (sin MFA).")
            return {"mfa_required": False, "access_token": access_token}
        else:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Contraseña de cliente incorrecta.")

    # 3. Flujo de inicio de sesión del técnico
    from backend.dao.technician_dao import TechnicianDAO
    tech = await TechnicianDAO.get_collection().find_one({
        "$or": [
            {"email": identifier},
            {"rut": normalized_identifier}
        ]
    })
    if tech:
        is_valid_pass = False
        if "password_hash" in tech:
            is_valid_pass = verify_password(password, tech["password_hash"])
        else:
            is_valid_pass = password in ["tech123", tech["rut"], "password123"]
            
        if is_valid_pass:
            requires_change = tech.get("requires_password_change", False)
            temp_token = create_access_token(
                data={
                    "sub": tech["email"], 
                    "role": "Tecnico", 
                    "mfa_pending": True,
                    "requires_password_change": requires_change
                },
                expires_delta=timedelta(minutes=5)
            )
            logger.info(f"Paso 1 de Login correcto para Técnico {tech['email']}. MFA requerido.")
            return {
                "mfa_required": True, 
                "temp_token": temp_token
            }
        else:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Contraseña de técnico incorrecta.")

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas o identificador no registrado.")


@router.post(
    "/step2",
    status_code=status.HTTP_200_OK,
    summary="Login Paso 2: Verificación de Código OTP (RF-021)",
    description="Valida el código de 6 dígitos. Si es correcto, emite el JWT definitivo de acceso."
)
async def login_step2(payload: LoginStep2DTO):
    # Decodificar token de acceso y verificar validez
    claims = decode_access_token(payload.temp_token)
    if not claims.get("mfa_pending"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token no válido para verificación de MFA")

    email = claims.get("sub")
    state = ADMIN_STATE.setdefault(email, {"failed_attempts": 0, "locked_until": None})

    # Verificar estado de bloqueo
    if state["locked_until"] and datetime.now(timezone.utc) < state["locked_until"]:
        delta = state["locked_until"] - datetime.now(timezone.utc)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cuenta bloqueada temporalmente por excesivos intentos fallidos de OTP. Intente en {int(delta.total_seconds())} segundos."
        )

    # Validar el código OTP (validación simulada: '000000' falla, cualquier otro dígito de 6 dígitos tiene éxito)
    if payload.code == "000000":
        state["failed_attempts"] += 1
        logger.warning(f"Intento fallido de OTP para {email}. Conteo: {state['failed_attempts']}")
        
        if state["failed_attempts"] >= 3:
            state["locked_until"] = datetime.now(timezone.utc) + timedelta(minutes=15)
            state["failed_attempts"] = 0  # Restablecer el contador para el próximo ciclo de bloqueo
            logger.error(f"Cuenta {email} bloqueada por 15 minutos.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Código OTP incorrecto. Cuenta bloqueada temporalmente por 15 minutos."
            )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Código OTP incorrecto. Intentos fallidos: {state['failed_attempts']}/3"
        )

    # OTP válida (cualquier código! = '000000')
    state["failed_attempts"] = 0
    state["locked_until"] = None

    role = claims.get("role", "Administrador")
    requires_change = claims.get("requires_password_change", False)
    name = "Administrador"

    if role == "Tecnico":
        from backend.dao.technician_dao import TechnicianDAO
        tech = await TechnicianDAO.get_collection().find_one({"email": email})
        if tech:
            requires_change = tech.get("requires_password_change", False)
            name = tech.get("name", "Técnico")
    elif role == "Administrador":
        name = "Admin"

    # Generar JWT definitivo
    access_token = create_access_token(
        data={
            "sub": email, 
            "role": role,
            "name": name,
            "requires_password_change": requires_change
        }
    )
    
    logger.info(f"Autenticación MFA exitosa para {email} ({role}). JWT emitido.")
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "requires_password_change": requires_change
    }