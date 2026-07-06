import os
import logging
import json
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pymongo.errors import PyMongoError, DuplicateKeyError

from backend.config.database import Database
from backend.dao.organization_dao import OrganizationDAO
from backend.dao.ticket_dao import TicketDAO
from backend.dao.technician_dao import TechnicianDAO
from backend.dao.user_dao import UserDAO
from backend.routes import organizations, tickets, technicians, dashboard, login, users, reports, feedback, analytics, gdpr, billing
from backend.middlewares.error_handler import global_exception_handler, AppError
from backend.tasks.sla_monitor import start_sla_monitor_loop

# ---------------------------------------------------------------------------
# Logging básico — Railway muestra stdout/stderr directamente en su dashboard
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("techhelp.main")


# ---------------------------------------------------------------------------
# Directorio de uploads: usar ruta absoluta basada en la ubicación del archivo
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR, "..", "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# CORS: leer orígenes desde variable de entorno CORS_ORIGINS o usar defaults
# ---------------------------------------------------------------------------
def _parse_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "")
    if raw:
        if raw.startswith("["):
            try:
                return json.loads(raw)
            except Exception:
                pass
        return [o.strip() for o in raw.split(",") if o.strip()]
    # Defaults: local dev + Netlify
    return [
        "http://localhost:5173",
        "https://techhelp-security.netlify.app",
    ]


# ---------------------------------------------------------------------------
# Lifespan: conexión a MongoDB + índices + tarea de fondo SLA
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle event manager: conecta la BD, crea índices e inicia el monitor SLA."""
    import asyncio

    logger.info("🚀 Iniciando TechHelp Backend...")
    logger.info(f"   MONGO_URI encontrada: {'SÍ' if os.getenv('MONGO_URI') or os.getenv('MONGO_URL') or os.getenv('MONGODB_URL') else 'NO — usando localhost fallback'}")

    # Conectar base de datos y crear índices
    Database.get_db()
    await OrganizationDAO.create_indexes()
    await TicketDAO.create_indexes()
    await TechnicianDAO.create_indexes()
    await UserDAO.create_indexes()

    # Iniciar tarea de monitoreo SLA en segundo plano
    asyncio.create_task(start_sla_monitor_loop())
    logger.info("✅ Backend listo. Monitor SLA iniciado.")

    yield

    # Limpieza al apagar
    Database.close_db()
    logger.info("🛑 Backend detenido. Conexión a MongoDB cerrada.")


# ---------------------------------------------------------------------------
# Aplicación FastAPI
# ---------------------------------------------------------------------------
app = FastAPI(
    title="TechHelp Backend API",
    description=(
        "Backend de la Plataforma de Soporte Técnico TechHelp. "
        "Incluye gestión de tickets, organizaciones y control de acceso (RBAC)."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# Static files (uploads)
# ---------------------------------------------------------------------------
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

# ---------------------------------------------------------------------------
# Middleware CORS
# ---------------------------------------------------------------------------
origins = _parse_cors_origins()
logger.info(f"CORS origins configurados: {origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Manejadores de excepciones globales
# ---------------------------------------------------------------------------
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(RequestValidationError, global_exception_handler)
app.add_exception_handler(AppError, global_exception_handler)
app.add_exception_handler(DuplicateKeyError, global_exception_handler)
app.add_exception_handler(PyMongoError, global_exception_handler)

# ---------------------------------------------------------------------------
# Rutas modulares
# ---------------------------------------------------------------------------
app.include_router(organizations.router, prefix="/api/v1")
app.include_router(tickets.router, prefix="/api/v1")
app.include_router(technicians.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(login.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(feedback.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(gdpr.router, prefix="/api/v1")
app.include_router(billing.router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# HealthCheck — Railway lo usa para verificar que el servicio está activo
# ---------------------------------------------------------------------------
@app.get("/", tags=["HealthCheck"], summary="Service Status Check")
async def health_check():
    """Verifica que el backend está activo. Usado por Railway para healthchecks."""
    return {"status": "healthy", "service": "TechHelp Backend"}