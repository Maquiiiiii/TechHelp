from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle event manager for database connection setup and indices indexing."""
    # Conexión de inicio
    Database.get_db()
    # Crear reglas de indexación
    await OrganizationDAO.create_indexes()
    await TicketDAO.create_indexes()
    await TechnicianDAO.create_indexes()
    await UserDAO.create_indexes()
    
    # Iniciar tareas en segundo plano
    import asyncio
    asyncio.create_task(start_sla_monitor_loop())
    
    yield
    # Conexión de limpieza al apagar
    Database.close_db()

# Inicialice la aplicación FastAPI con descripciones personalizadas de Swagger
app = FastAPI(
    title="TechHelp Backend API",
    description="Backend de la Plataforma de Soporte Técnico TechHelp. "
                "Incluye gestión de tickets, organizaciones y control de acceso (RBAC).",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

from fastapi.staticfiles import StaticFiles
import os

# Asegúrese de que existe el directorio de cargas
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Configure el middleware CORS para habilitar la integración frontend (solicitudes de OPCIONES de verificación previa)
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://techhelp-security.netlify.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro de controladores de excepciones personalizados a nivel mundial
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(RequestValidationError, global_exception_handler)
app.add_exception_handler(AppError, global_exception_handler)
app.add_exception_handler(DuplicateKeyError, global_exception_handler)
app.add_exception_handler(PyMongoError, global_exception_handler)

# Registrador de rutas modulares
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

@app.get("/", tags=["HealthCheck"], summary="Service Status Check")
async def health_check():
    """Verify application status."""
    return {"status": "healthy", "service": "TechHelp Backend"}