import os
import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv

# Carga variables ambientales
load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET", "supersecretjwtkeytechhelp2026!")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# Esquema de seguridad HTTPBearer
security = HTTPBearer()

def hash_password(password: str) -> str:
    """Hash password using bcrypt with cost 12."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify standard plain password against its hashed representation."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """Generate JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token."""
    import logging
    log = logging.getLogger("techhelp.security.auth")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError as e:
        log.warning(f"JWT Verification Failed: Token has expired. Token: {token[:15]}... Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token ha expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        log.warning(f"JWT Verification Failed: Invalid token. Token: {token[:15]}... Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Dependency injection payload to retrieve active logged in user from JWT."""
    payload = decode_access_token(credentials.credentials)
    role = payload.get("role")
    if role == "Cliente":
        rut = payload.get("organization_rut") or payload.get("rut")
        email = payload.get("sub")
        
        from backend.config.database import Database
        db = Database.get_db()
        
        org_query = {}
        if rut:
            org_query["rut"] = rut
        elif email:
            org_query["email"] = email
            
        if org_query:
            org = await db["organizations"].find_one(org_query)
            if org and org.get("activo", True) is False:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cuenta bloqueada: su organización ha sido desactivada."
                )
    return payload

class RoleChecker:
    """RBAC validation checks for paths/controllers."""
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: dict = Depends(get_current_user)) -> dict:
        role = user.get("role")
        if not role or role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: no posee privilegios suficientes para este endpoint"
            )
        return user