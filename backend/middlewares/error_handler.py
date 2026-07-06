import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pymongo.errors import PyMongoError, DuplicateKeyError

# Configurar registrador
logger = logging.getLogger("techhelp.errors")
logging.basicConfig(level=logging.INFO)

class AppError(Exception):
    """Base application exception for TechHelp."""
    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

class DuplicateResourceError(AppError):
    """Exception raised when an entity already exists (e.g. RUT or Email duplicate)."""
    def __init__(self, message: str):
        super().__init__(message, status_code=status.HTTP_409_CONFLICT)

class ConcurrencyError(AppError):
    """Exception raised when an OCC check fails."""
    def __init__(self, message: str = "Control de concurrencia: el documento fue modificado por otro proceso."):
        super().__init__(message, status_code=status.HTTP_409_CONFLICT)

async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception interceptor that hides server tracebacks and formats JSON errors."""
    
    # Errores de aplicaciones personalizadas
    if isinstance(exc, AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.message, "code": exc.status_code}
        )
    
    # Errores de validación de FastAPI/Pydantic
    if isinstance(exc, RequestValidationError):
        errors_list = []
        for err in exc.errors():
            # Obtenga la ruta/ubicación del campo no válida
            field_path = " -> ".join(str(loc) for loc in err.get("loc", []) if loc != "body")
            msg = err.get("msg", "Formato inválido")
            errors_list.append(f"{field_path}: {msg}" if field_path else msg)
        
        error_msg = f"Error de validación: {'; '.join(errors_list)}"
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": error_msg, "code": status.HTTP_422_UNPROCESSABLE_ENTITY}
        )

    # Errores de clave duplicada de MongoDB (restricciones de unicidad a nivel de base de datos)
    if isinstance(exc, DuplicateKeyError):
        logger.warning(f"Database DuplicateKeyError: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": "Ya existe un registro con esos datos (RUT o Email duplicados)", "code": status.HTTP_409_CONFLICT}
        )

    # Errores generales de conexión/operación de la base de datos
    if isinstance(exc, PyMongoError):
        logger.error(f"Database error: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Error interno al procesar la base de datos", "code": status.HTTP_500_INTERNAL_SERVER_ERROR}
        )

    # Todas las demás excepciones de Python no controladas
    logger.error(f"Unhandled server error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Error interno del servidor", "code": status.HTTP_500_INTERNAL_SERVER_ERROR}
    )