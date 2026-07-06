# context.md — Bitácora del Proyecto: Plataforma TechHelp

> Registro continuo de decisiones técnicas y artefactos del desarrollo de la plataforma corporativa TechHelp de extremo a extremo.

---

## Metadatos del Proyecto

| Campo | Valor |
| :--- | :--- |
| **Proyecto** | Plataforma TechHelp — Sistema Corporativo de Gestión de Tickets de Soporte |
| **Inicio** | Julio 2026 |
| **Stack Backend** | Python, FastAPI, Motor (driver asíncrono MongoDB), Pydantic (DTOs) |
| **Base de Datos** | MongoDB Atlas (nube) / MongoDB 6.0 local (desarrollo) |
| **Stack Frontend** | React, Vite, Zustand (estado global), TailwindCSS, Recharts, VitePWA |
| **Infraestructura** | Docker, Docker Compose (local + Atlas) |

---

## Estructura de Carpetas

```
c:\Users\villa\Downloads\TechHelp\
 ├── context.md                    # Bitácora oficial de arquitectura e historial del proyecto
 ├── docker-compose.yml            # Orquestación de infraestructura Docker
 ├── backend/
 │    ├── main.py                  # Entrypoint FastAPI (registro de rutas, CORS y lifecycles)
 │    ├── requirements.txt         # Dependencias backend (FastAPI, Motor, Pydantic, Bcrypt, PyJWT, multi-part)
 │    ├── .env                     # Variables de entorno locales
 │    ├── Dockerfile               # Contenedor de Docker para el backend
 │    ├── config/
 │    │    └── database.py         # Inicializador y pool asíncrono de base de datos MongoDB
 │    ├── middlewares/
 │    │    └── error_handler.py    # Interceptor global de excepciones (sin fugas de stack trace)
 │    ├── security/
 │    │    └── auth.py             # Lógica de cifrado (bcrypt) y firma/verificación de tokens JWT
 │    ├── dto/
 │    │    ├── organization_dto.py # Validaciones Pydantic y RUT para organizaciones
 │    │    ├── ticket_dto.py       # DTOs para creación de tickets y reglas de estados
 │    │    └── technician_dto.py   # DTOs de técnicos y disponibilidad
 │    ├── dao/
 │    │    ├── organization_dao.py # DAO de Organizaciones (CRUD y OCC __v)
 │    │    ├── ticket_dao.py       # DAO de Tickets (Máquina de estados, autoasignación, comentarios y adjuntos)
 │    │    ├── technician_dao.py   # DAO de Técnicos (Contador secuencial y estados)
 │    │    ├── log_dao.py          # DAO de Bitácora Forense (RF-014)
 │    │    └── dashboard_dao.py    # DAO de Métricas del Dashboard (Pipeline de agregación MongoDB)
 │    ├── routes/
 │    │    ├── organizations.py    # Endpoints de Organizaciones (POST/PUT/GET)
 │    │    ├── tickets.py          # Endpoints de Tickets (POST/PUT/GET, comments y attachments)
 │    │    ├── technicians.py      # Endpoints de Técnicos (POST/PUT/GET)
 │    │    ├── dashboard.py        # Endpoints analíticos y logs (GET /metrics, GET /logs)
 │    │    └── login.py            # Endpoints de autenticación (Login 2-Step y MFA OTP)
 │    ├── tasks/
 │    │    └── sla_monitor.py      # Tarea en segundo plano de alerta de vencimiento de SLA (FastAPI lifespan)
 │    ├── tests/                   # Suite de pruebas automatizadas pytest (35 casos exitosos)
 │    └── venv/                    # Entorno virtual de Python aislado
 └── frontend/
      ├── index.html               # Entrada del cliente
      ├── package.json             # Dependencias (react-router-dom, axios, zustand, tailwindcss, recharts, lucide-react)
      ├── tailwind.config.js       # Configuración del tema corporativo oscuro en Tailwind CSS
      ├── postcss.config.js        # PostCSS
      ├── vite.config.js           # Configuración del empaquetador Vite con el plugin de PWA y Workbox
      └── src/
           ├── App.jsx             # Punto de entrada de la aplicación React
           ├── index.css           # Carga de Tailwind CSS y animaciones CSS de blobs y keyframes
           ├── components/
           │    └── ProtectedRoute.jsx # Guardián de rutas autenticadas en Zustand
           ├── layouts/
           │    └── DashboardLayout.jsx # Contenedor principal con sidebar RBAC y banner offline
           ├── store/
           │    └── authStore.js   # Manejo global y persistencia de sesión Zustand
           ├── utils/
           │    └── api.js         # Cliente Axios centralizado con interceptores de seguridad
           ├── routes/
           │    └── AppRouter.jsx  # Mapa central de enrutamiento (públicas y protegidas)
           └── pages/
                ├── Login.jsx      # Pantalla de Login Cardless con auroras morphing LERP
                ├── Dashboard.jsx  # Métricas mensuales y gráficos BarChart de Recharts
                ├── TicketsList.jsx# Listado de incidentes con badges de estados y prioridades
                ├── CreateTicket.jsx # Formulario con contador de caracteres y validaciones en caliente
                ├── TicketDetail.jsx # Detalle del ticket con transición de estados, comentarios y adjuntos
                ├── Organizations.jsx # Consola CRUD de Organizaciones clientes
                ├── Technicians.jsx# Consola CRUD de Técnicos resolutores
                └── Audit.jsx      # Listado de logs de auditoría forense e IPs
```

---

## Registro Cronológico

### ## Paso 1 — Inicialización del Proyecto y Backend Core (RBAC, SLA, OCC)
**Fecha:** Julio 2026

#### Qué se construyó

| Artefacto | Descripción |
| :--- | :--- |
| database.py | Establece conexión asíncrona a base de datos usando Motor. |
| error_handler.py | Captura excepciones globables y de concurrencia formateándolas uniformemente. |
| auth.py | Encapsula BCrypt y generación de tokens JWT. |
| dto/organization_dto.py | DTOs para organizaciones, incluyendo validación de RUT y `tier_contractual` (RF-024). |
| dao/organization_dao.py | DAO para organizaciones con validación de RUT único, OCC y persistencia de `tier_contractual` (RF-024). |
| dto/ticket_dto.py | DTOs para tickets y `AuditLogDTO` (RF-014). |
| dao/ticket_dao.py | Lógica de la máquina de estados, acumulador de pausa de SLA, inyección de auditoría y cálculo dinámico de SLA basado en `tier_contractual` (RF-024). |
| dao/technician_dao.py | Asignación secuencial autoincremental de IDs de técnicos y control de disponibilidad. |
| dao/log_dao.py | DAO de Bitácora Forense (RF-014) con manejo de inmutabilidad, serialización de `ObjectId` y métodos de consulta. |
| dao/dashboard_dao.py | DAO de Métricas del Dashboard, incluyendo pipeline de agregación para Alerta de Churn (RF-025). |
| utils/sla_matrix.py | Matriz de definición de ventanas de SLA por `tier_contractual` y prioridad (RF-024). |
| tasks/sla_monitor.py | Tarea en segundo plano de alerta de vencimiento de SLA (FastAPI lifespan). |
| `01_init_rbac.js` | Script de inicialización de MongoDB para configurar RBAC: `auditLoggerRole` (insert/find en `audit_logs`) y `techhelp_app_user`. |

#### Decisiones Técnicas Clave
1. **Control de Concurrencia Optimista (OCC):** Uso obligatorio del campo entero secuencial `__v` en lugar de bloqueos de tabla pesados para garantizar atomicidad y prevenir colisiones bajo alta concurrencia.
2. **ANS (SLA) Calculado en DAO:** Para optimizar la lectura de base de datos, el cálculo de las pausas de SLA se almacena en el ticket incrementando `minutos_en_espera_acumulados` con `$inc` al salir del estado `En Espera`. El cálculo de la fecha de expiración del SLA considera el `tier_contractual` de la organización (RF-024). Está prohibido leer `audit_logs` dentro del loop de SLA.
3. **Inmutabilidad de `audit_logs` (RNF-SEG-004):** Implementación de un rol de MongoDB (`auditLoggerRole`) que permite estrictamente `insert` y `find` en la colección `audit_logs`, bloqueando `update`, `remove` y `dropCollection` a nivel de base de datos.

#### Reglas de Negocio / Endpoints

| Ruta / Método | Permisos | Regla Lógica / Validación |
| :--- | :--- | :--- |
| `POST /organizations` | Administrador | Registra una nueva organización, incluyendo su `tier_contractual` (RF-024). |
| `POST /tickets` | Cliente / Administrador | Valida que la descripción tenga al menos 20 caracteres. Inicializa estado en `Abierto`. Calcula dinámicamente el SLA, con excepción de 30 minutos para "Oro" + "Alta" (RF-024). |
| `PUT /tickets/{id}/status` | Técnico / Administrador | Valida transiciones lícitas de estados. Requiere `comentario_solucion` para resolver y `justificacion_pausa` para pausar. Registra eventos en la bitácora forense (RF-014). |
| `POST /users/client` | Administrador | Valida existencia de la organización y unicidad del email. Dispara el envío de correo de activación de forma asíncrona mediante BackgroundTasks. |
| `PUT /tickets/{id}/re-route` | Técnico / Administrador | Re-ruta, rechaza o recategoriza un ticket. Si se recategoriza, resetea SLA, limpia asignado y vuelve a 'Abierto'. Si no, pasa a 'Rechazado' de forma permanente. |
| `PUT /tickets/{id}/priority` | Administrador | Reclasifica la prioridad de un ticket y recalcula la fecha de expiración del SLA a partir del momento exacto del cambio (evitando vencimientos retroactivos), considerando el `tier_contractual` (RF-024). Requiere justificación (min 10 caracteres). |
| `GET /reports/mttr` | Administrador | Genera y descarga un archivo CSV con las estadísticas de volumen resuelto y MTTR en minutos de cada técnico para un rango de fechas. |
| `POST /feedback` | Público | Registra encuestas de satisfacción de clientes vinculándolas al técnico resolutor sin mutar el ticket original. Valida token de 48 horas de vida útil. |
| `GET /analytics/churn-risk` | Administrador | Detecta clientes en riesgo de cancelación mediante cruces complejos NoSQL de violaciones de SLA (>15%) y evaluaciones (<2.5) en los últimos 14 días. |
| `GET /analytics/capacity-projection` | Administrador | Analiza tendencias e inyecta alertas de contratación técnica si la demanda de incidentes cerrados crece sostenidamente más de un 20% mensual (min 3 meses). |
| `DELETE /users/client/{id}/anonymize` | Administrador | Anonimiza de forma irreversible y conforme a la GDPR el nombre e email del usuario cliente sin alterar las estadísticas históricas de tickets. |
| `POST /billing/transactions` | Público | Registra una transacción de cobro simulada para Webpay Plus, retornando un token criptográfico y URL de redirección. |
| `PUT /billing/transactions/{token}` | Público | Confirma la transacción con Transbank, actualizando la factura interna a estado 'Pagado' (bloqueando cobros repetidos). |


#### Comandos para ejecutar y probar

```bash
# ── DESARROLLO LOCAL (MongoDB en contenedor) ──────────────────────────────
# Levantar todos los servicios (backend + MongoDB local)
docker-compose up --build -d

# Ver logs del backend en tiempo real
docker logs -f techhelp_backend

# Ver estado de los contenedores
docker ps

# Detener todos los servicios
docker-compose down

# Detener y borrar volúmenes (reset total de BD)
docker-compose down -v

# ── PRODUCCIÓN CON ATLAS ──────────────────────────────────────────────────
# 1. Editar .env.atlas con las credenciales reales de Atlas:
#    MONGO_URI=mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/techhelp_db?retryWrites=true&w=majority
#    JWT_SECRET=<clave-secreta-segura>

# 2. Levantar solo el backend (sin MongoDB local)
docker-compose -f docker-compose.atlas.yml up --build -d

# 3. Ver logs de producción
docker logs -f techhelp_backend_prod

# ── PRUEBAS AUTOMATIZADAS ─────────────────────────────────────────────────
# Ejecutar tests (requiere venv activo y MongoDB corriendo)
.\backend\venv\Scripts\python -m pytest backend\tests -v

# ── URLS ÚTILES ───────────────────────────────────────────────────────────
# Swagger UI: http://localhost:8000/docs
# ReDoc:      http://localhost:8000/redoc
# Healthcheck: http://localhost:8000/
```

#### Archivos Docker del proyecto

| Archivo | Propósito |
| :--- | :--- |
| `backend/Dockerfile` | Imagen Python 3.11-slim. Instala deps, copia código en `/app/backend/`, crea `/app/uploads/`. |
| `backend/.dockerignore` | Excluye `venv/`, `__pycache__/`, `.env`, `tests/` del contexto de build (build más rápido). |
| `docker-compose.yml` | **Desarrollo local**: backend + MongoDB 6.0 en contenedor. Healthcheck en Mongo antes de arrancar el backend. |
| `docker-compose.atlas.yml` | **Producción con Atlas**: solo el backend. Lee credenciales desde `.env.atlas`. Sin contenedor MongoDB. |
| `.env.atlas` | Template de variables de entorno para Atlas. **Nunca subir a Git** (está en `.gitignore`). |

#### Cómo conectar con MongoDB Atlas

1. Crear un cluster gratuito en [cloud.mongodb.com](https://cloud.mongodb.com)
2. En **Database Access** → crear un usuario con permisos `readWrite` en `techhelp_db`
3. En **Network Access** → añadir `0.0.0.0/0` (o la IP del servidor de despliegue)
4. Copiar el **Connection String** (`mongodb+srv://...`) al archivo `.env.atlas`
5. Ejecutar: `docker-compose -f docker-compose.atlas.yml up --build -d`

#### Notas / Pendientes
* Configurar la base de datos para restringir la escritura a `audit_logs` a nivel de roles de MongoDB.
* El script `01_init_rbac.js` solo aplica en entorno local (MongoDB en contenedor). En Atlas, crear el rol `auditLoggerRole` manualmente desde la UI o con `mongosh` conectado a Atlas.

---

### ## Paso 2 — Setup del Frontend, Ruteo y Autenticación
**Fecha:** Julio 2026

#### Qué se construyó

| Artefacto | Descripción |
| :--- | :--- |
| [api.js](file:///c:/Users/villa/Downloads/TechHelp/frontend/src/utils/api.js) | Cliente Axios con interceptores de inyección JWT y control de expiraciones (401/403). |
| [authStore.js](file:///c:/Users/villa/Downloads/TechHelp/frontend/src/store/authStore.js) | Store Zustand con persistencia en localStorage para almacenar sesión y MFA temporal. |
| [Login.jsx](file:///c:/Users/villa/Downloads/TechHelp/frontend/src/pages/Login.jsx) | Interfaz en dos pasos (Login + MFA OTP). Auroras dinámicas usando LERP sobre el DOM. |
| [AppRouter.jsx](file:///c:/Users/villa/Downloads/TechHelp/frontend/src/routes/AppRouter.jsx) | Rutas protegidas configuradas mediante react-router-dom. |

#### Decisiones Técnicas Clave
1. **Diseño Cardless e Inputs Transparentes:** Adopción estricta de una estética minimalista sin tarjetas blancas para dar protagonismo a la malla de luces de fondo.
2. **Optimización Aurora LERP Directa:** Para prevenir caídas de FPS, se descartaron los estados de React en eventos de mouse y se modificó directamente `translate3d` de los divs de luz mediante referencias de React (`useRef`).

#### MFA Gerencial para Administradores y Bypass para Roles (RF-021)
El inicio de sesión de los usuarios varía según su rol para facilitar las pruebas del sistema:
1.  **Administrador (`admin@techhelp.cl`):** Consta de dos etapas obligatorias:
    *   **Paso 1:** Validación de credenciales básicas (`admin123`). Retorna un JWT de tipo temporal con el flag `mfa_pending = True`.
    *   **Paso 2:** Verificación de código OTP de 6 dígitos. Si el código OTP ingresado es `'000000'`, se asume fallido de manera explícita. Si se registran 3 intentos fallidos consecutivos, el sistema bloquea temporalmente la cuenta por **5 minutos** (HTTP `403 Forbidden`).
2.  **Cliente (Organización):** Se busca el correo directamente en la colección de organizaciones. Permite iniciar sesión directamente (sin segundo paso de MFA) ingresando la contraseña por defecto `client123` o el **RUT** de la organización.
3.  **Técnico (Technician):** Se busca el correo en la colección de técnicos. Permite iniciar sesión directamente (sin segundo paso de MFA) ingresando la contraseña por defecto `tech123` o el **RUT** del técnico.

---

#### Comandos para ejecutar y probar
```bash
# Instalar dependencias del frontend
cd frontend
npm install

# Levantar servidor de desarrollo
npm run dev
```

#### Notas / Pendientes
* Registrar e implementar las vistas de Tickets en el ruteador de la aplicación.

---

### ## Paso 3 — Módulos de Tickets (Creación, Listado y Detalle)
**Fecha:** Julio 2026

#### Qué se construyó

| Artefacto | Descripción |
| :--- | :--- |
| [TicketsList.jsx](file:///c:/Users/villa/Downloads/TechHelp/frontend/src/pages/TicketsList.jsx) | Tabla de tickets con colores dinámicos de estados y prioridad. |
| [CreateTicket.jsx](file:///c:/Users/villa/Downloads/TechHelp/frontend/src/pages/CreateTicket.jsx) | Formulario de creación de incidentes con validación e indicador de caracteres en tiempo real. |
| [TicketDetail.jsx](file:///c:/Users/villa/Downloads/TechHelp/frontend/src/pages/TicketDetail.jsx) | Detalle del ticket, controles de la máquina de estados, notas públicas/internas y adjuntos. |

#### Decisiones Técnicas Clave
1. **Validación de Adjuntos en Cliente (RF-006):** Para mitigar sobrecargas de red, el frontend intercepta y rechaza archivos > 5MB y extensiones distintas a PDF, PNG y JPG antes de llamar a la API.
2. **Formulario Inline para Transiciones:** Se integraron áreas de texto de confirmación obligatoria directo en el panel de acciones al pausar o resolver, evitando modales invasivos y manteniendo el estilo limpio.

#### Reglas de Negocio / Endpoints

| Ruta / Método | Acción | Regla Lógica / Validación |
| :--- | :--- | :--- |
| `POST /tickets/{id}/attachments` | Subir archivo | Limita binarios en base de datos. Solo guarda URL ficticia generada: `https://storage.techhelp.com/...` |
| `POST /tickets/{id}/comments` | Agregar comentario | Si el rol es `Cliente`, el backend y frontend filtran comentarios donde `es_interno = True`. |

#### Comandos para ejecutar y probar
```bash
# Compilar la aplicación React para producción
cd frontend
npm run build
```

#### Notas / Pendientes
* Implementar consolas de administración para organizaciones, técnicos y dashboard métrico.

---

### ## Paso 4 — Dashboard y Consolas de Administración
**Fecha:** Julio 2026

#### Qué se construyó

| Artefacto | Descripción |
| :--- | :--- |
| [Dashboard.jsx](file:///c:/Users/villa/Downloads/TechHelp/frontend/src/pages/Dashboard.jsx) | Dashboard métrico con indicadores clave de rendimiento y gráficos BarChart de Recharts. |
| [Organizations.jsx](file:///c:/Users/villa/Downloads/TechHelp/frontend/src/pages/Organizations.jsx) | CRUD de organizaciones cliente de TechHelp con formulario modal de alta. |
| [Technicians.jsx](file:///c:/Users/villa/Downloads/TechHelp/frontend/src/pages/Technicians.jsx) | CRUD de personal de soporte técnico con controles de especialidad y estado de disponibilidad. |
| [Audit.jsx](file:///c:/Users/villa/Downloads/TechHelp/frontend/src/pages/Audit.jsx) | Lista histórica de transiciones de estados (Auditoría Forense con timestamp e IPs). |

#### Decisiones Técnicas Clave
1. **Bloqueo y Seguridad RBAC en Componente:** Si un usuario burla la barra de navegación e ingresa a una ruta privilegiada, el componente detecta el rol no autorizado desde Zustand, deteniendo la llamada HTTP del backend y desplegando un banner de acceso denegado.
2. **Recharts en Modo Oscuro:** Se estilizaron tooltips y leyendas del gráfico de barras para integrarse con la estética general.

#### Reglas de Negocio / Endpoints

| Ruta / Método | Permisos | Regla Lógica / Validación |
| :--- | :--- | :--- |
| `GET /dashboard/metrics` | Administrador | Devuelve estadísticas acumuladas del mes en curso ordenados por estado. |
| `GET /dashboard/logs` | Administrador | Bitácora forense de transiciones. Retorna IP de red y precisión de milisegundos. |

#### Comandos para ejecutar y probar
```bash
# Iniciar las pruebas automatizadas del backend para corroborar endpoints de administración
.\backend\venv\Scripts\python -m pytest backend\tests
```

#### Notas / Pendientes
* Implementar estrategias de caché y Service Workers offline para soporte móvil en terreno.

---



### ## Paso 6 — Módulos Analíticos y Mejoras de Administración
**Fecha:** Julio 2026

#### Qué se construyó

| Artefacto | Descripción |
| :--- | :--- |
| Dashboard.jsx | Integración del Panel Analítico Predictivo de Alerta Temprana de Churn (RF-025) y Proyección de Capacidad Técnica Operativa (RF-026) con Recharts, filtros y alertas visuales. |
| Organizations.jsx | Formulario de creación/edición de organizaciones actualizado con selección obligatoria de `tier_contractual` (RF-024). |

#### Decisiones Técnicas Clave
1. **Alerta de Churn (RF-025):** Implementación de un panel visual para organizaciones en riesgo de abandono, con indicadores de `riesgo_inminente` y funcionalidad de exportación de contactos a CSV.
2. **Proyección de Capacidad (RF-026):** Visualización de tendencias de incidentes por especialidad vs. capacidad real, con alertas de contratación si la demanda supera los límites saludables.
3. **Validación Frontend de `tier_contractual` (RF-024):** El botón de guardar en el formulario de organizaciones se deshabilita hasta que se selecciona un nivel de soporte contractual válido.

---

### ## Paso 7 — Almacenamiento Local de Adjuntos, Layout Premium de Cabecera/Sidebar y Refrescos de Datos
**Fecha:** Julio 2026

#### Qué se construyó

| Artefacto | Descripción |
| :--- | :--- |
| main.py | Registro y montaje del directorio `/uploads` como ruta estática en FastAPI. |
| routes/tickets.py | Guardado físico real de archivos adjuntos en el servidor y generación de URLs locales. |
| TicketDetail.jsx | Atributo `download` en los enlaces de adjuntos para forzar descargas nativas del navegador. |
| DashboardLayout.jsx | Sidebar premium fija `#14171a` con indicador azul, logo pulsante y Topbar reorganizada: `[Badge] -> [Text (right)] -> [Avatar]`. |
| Dashboard.jsx | Hook de refresco automático silencioso cada 60s en segundo plano con descarte de fugas. |
| Organizations.jsx / Technicians.jsx / Audit.jsx | Botones de refresco manual con animación `animate-spin` y alturas ajustadas milimétricamente. |

#### Decisiones Técnicas Clave
1. **Estrategia de Adjuntos Locales:** Se sustituyó la URL estática `storage.techhelp.com` por un almacenamiento físico real en `/uploads` y enlaces absolutos al localhost para garantizar descargas reales y resolver el error de DNS.
2. **Alineación Simétrica de Alturas (Pixel-Perfect):** Se homologaron las alturas de la barra de búsqueda y del botón de actualización a una altura exacta de `h-10` en Organizations, `w-8 h-8` en Technicians y `w-9 h-9` en Audit para garantizar una consistencia milimétrica.
3. **Refrescos No Invasivos:** En el dashboard se optó por un refresco silencioso sin spinner invasivo para no interrumpir la navegación del usuario administrador.

---

### ## Paso 8 — Segmentación de Organizaciones por Tickets en el Dashboard
**Fecha:** Julio 2026

#### Qué se construyó

| Artefacto | Descripción |
| :--- | :--- |
| dashboard_dao.py | Pipeline de agregación MongoDB `$lookup` y `$match` para filtrar organizaciones por rango de tickets acumulados. |
| dashboard.py | Endpoint `GET /dashboard/organizations-by-ticket-count` con filtros `tickets_min`/`tickets_max` y RBAC de Administrador. |
| Dashboard.jsx | Panel de búsqueda y sub-tabla de segmentación de organizaciones con validación en caliente y simetría pixel-perfect `h-10`. |
| test_analytics.py | Caso de prueba de integración `test_organizations_by_ticket_count_filter` para verificar la segmentación de tickets y RBAC. |

#### Decisiones Técnicas Clave
1. **Validación Frontend de Rangos Inválidos:** Se agregó lógica para que si `ticketsMax` es menor que `ticketsMin` (y ambos campos están completos), se deshabilite el botón "Filtrar" y se muestre un aviso en color rojo.
2. **Consistencia de Rut vs. Customer ID:** La agregación asocia las colecciones `organizations` y `tickets` relacionando el campo local `rut` con el remoto `customer_id` para garantizar que no se pierdan datos y que el conteo de incidentes acumulados sea preciso.

### ## Paso 9 — Borrado Lógico de Organizaciones y Bloqueo de Sesiones en Cascada
**Fecha:** Julio 2026

#### Qué se construyó

| Artefacto | Descripción |
| :--- | :--- |
| organization_dto.py | Adición de propiedad `activo` a `OrganizationResponseDTO` y cambio de `industria` a opcional. |
| organization_dao.py | Adición de migración de inicio, métodos `delete` lógico y `toggle_status` con cascade de cierre de tickets activos y auditoría forense. |
| auth.py | Modificación de `get_current_user` a async con bloqueo HTTP 403 Forbidden para clientes de organizaciones desactivadas. |
| login.py / tickets.py | Bloqueo de login de clientes inactivos (HTTP 403) e inyección de claim en token JWT, y bloqueo de comentarios en tickets de orgs inactivas (HTTP 400). |
| Organizations.jsx | Tabla con switch de candado (`Lock`/`Unlock`) y colores verde/rojo pixel-perfect `inline-flex`. |
| api.js / ProtectedRoute.jsx | Interceptor de error 403 para forzar redirección, y guard para impedir navegación interna mandándolos a `/blocked`. |
| AccountBlocked.jsx / AppRouter.jsx | Página premium oscura con radial glows rojos y registro de ruta `/blocked`. |
| test_deletion.py | Caso de prueba `test_organization_delete_constraints` adaptado a la deactivación lógica y cierre en cascada. |

#### Decisiones Técnicas Clave
1. **Auditoría Forense en Cierre Cascada:** El cierre cascada por deactivación actualiza `status` a "Cerrado", calcula y adiciona el tiempo acumulado en espera si el ticket estaba pausado ("En Espera"), y agrega una bitácora con autor "Sistema" para auditoría.
2. **Dependencia get_current_user Async:** Se cambió la firma a `async def` para permitir consultas asíncronas de base de datos en MongoDB.
3. **Estilo del Toggle y Altura Pixel-Perfect:** El nuevo botón de candados conserva exactamente las clases `inline-flex items-center justify-center p-1.5 transition duration-150 rounded border` para evitar asimetrías visuales en las filas.

---

## Datos de Entrada

*   **Nombre del Proyecto:** Plataforma TechHelp — Gestión Corporativa de Soporte Técnico
*   **Stack:** Python, FastAPI, MongoDB (Motor), Pydantic, React (Vite), Zustand, TailwindCSS, Recharts, VitePWA
*   **Resumen del Paso a documentar:** Hemos estructurado y completado la plataforma de soporte TechHelp de extremo a extremo: enrutamiento y auth JWT con 2-step TOTP MFA (Paso 1 y Paso 2), base de datos MongoDB con control de concurrencia optimista (OCC) por versión `__v`, listados, creación y detalle de tickets interactivos con transiciones de máquina de estados y subida de archivos adjuntos, consolas de administración para organizaciones y técnicos, dashboard métrico gerencial con Recharts y soporte PWA offline con estrategia NetworkFirst.

---

## Historial de Errores Resueltos Recientemente

Esta sección documenta los errores significativos que fueron identificados y corregidos durante el desarrollo reciente, asegurando la estabilidad y funcionalidad del proyecto.

| Error Identificado | Archivo(s) Afectado(s) | Descripción y Solución |
| :--- | :--- | :--- |
| `ImportError: cannot import name 'AuditLogDAO'` | `backend/routes/dashboard.py`, `backend/dao/log_dao.py` | La clase `AuditLogDAO` fue renombrada a `LogDAO`. Se actualizó la importación en `dashboard.py` y se añadió el método `get_recent` a `LogDAO` para compatibilidad. |
| `TypeError: 'ObjectId' object is not iterable` | `backend/dao/log_dao.py`, `backend/dao/dashboard_dao.py` | FastAPI no puede serializar directamente los objetos `ObjectId` de MongoDB a JSON. Se modificaron los métodos `get_all` y `get_recent` en `LogDAO`, y los métodos de `DashboardDAO` que retornaban documentos de MongoDB, para convertir explícitamente `_id` a `str` antes de devolver los documentos. |
| Inconsistencia en campo `tier_contractual` | `backend/dto/organization_dto.py`, `backend/dao/organization_dao.py`, `backend/routes/organizations.py` | Se corrigió la inconsistencia donde el DTO y la ruta de la API aún usaban `nivel_soporte` en lugar de `tier_contractual`. Se actualizó el DTO, el DAO y la ruta para usar `tier_contractual` de forma consistente. |
| `TypeError: Cannot read properties of undefined (reading 'length')` (Pantalla gris del Admin) | `frontend/src/pages/Dashboard.jsx` | La API de proyección de capacidad retornaba `projections` pero el componente del panel intentaba desestructurar `projection_data` y `hiring_alerts` resultando en un error de tipo en tiempo de ejecución. Se implementó una función transformadora para aplanar la demanda por categoría a meses cronológicos apta para Recharts y se ajustaron los query params a `rango_meses`. |
| Cierre de sesión involuntario al presionar F5 | `frontend/src/App.jsx`, `frontend/src/store/authStore.js`, `frontend/src/components/ProtectedRoute.jsx` | `App.jsx` invocaba la acción de `logout()` en cada ciclo de montaje, destruyendo el token al recargar. Se eliminó la llamada forzada a `logout` en el montaje inicial y se añadió la propiedad `hasHydrated` en la store de autenticación para que el enrutador no expulse al usuario en el refresco. |
| Bloqueo temporal del OTP por 15 minutos | `backend/routes/login.py` | La ventana de bloqueo temporal para cuentas de administrador con 3 intentos fallidos consecutivos de MFA estaba configurada en 5 minutos. Se ajustó el delta de expiración a exactamente 15 minutos en el paso 2 de inicio de sesión. |
| RUT de organización vacío en alerta de Churn | `frontend/src/pages/Dashboard.jsx`, `backend/dto/analytics_dto.py`, `backend/dao/analytics_dao.py` | La tabla analítica de Churn esperaba `org.organization_rut` pero la API analítica retornaba `customer_id`. Se reconfiguró el fetcher en el frontend para mapear el RUT y los campos del DTO (SLA a porcentaje entero, rating y email), y se proyectó el campo de correo de contacto desde la base de datos de organizaciones en la pipeline del backend. |

| Acceso de Técnicos sin MFA | `backend/routes/login.py` | Se eliminó el bypass de inicio de sesión directo para técnicos. Ahora pasan obligatoriamente por el Step 2 (TOTP de 6 dígitos) y los errores de verificación de OTP retornan HTTP 401. |
| Inactividad de sesión no controlada | `frontend/src/store/authStore.js` | Se inyectó un listener de inactividad de 15 minutos que cierra sesión para roles Técnico y Admin. Las llamadas se controlan con una función `throttle` para no degradar el rendimiento por eventos de mouse/scroll continuos. |
| Validación de código de ticket débil | `backend/dto/ticket_dto.py` | Se añadió un `@field_validator` de Pydantic para validar estrictamente que todos los códigos de ticket cumplan con la regex `^TK-[0-9]{5}$`. |
| Autoasignación no ponderada / con empates | `backend/dao/ticket_dao.py`, `backend/utils/routing_algorithm.py` | Se creó un algoritmo ponderado independiente que evalúa la carga ponderando tickets activos (Baja=1, Media=2, Alta/Crítica=3) y desempatando por el técnico cuya última asignación sea la más antigua. |
| Centralización de Cron Jobs y control de comentarios | `backend/tasks/sla_monitor.py`, `backend/main.py` | Se eliminó `ticket_closer.py` y se movió el auto-cierre de tickets Resueltos a `sla_monitor.py`. Ahora se valida que no existan comentarios nuevos de clientes en los últimos 5 días hábiles antes de mutar el ticket a Cerrado. |
| Notificación de nota pública e intervalo de estrellas | `backend/routes/tickets.py`, `backend/utils/email_sender.py`, `backend/dto/feedback_dto.py` | Se gatilla un email asíncrono al cliente cuando un técnico añade un comentario público. Se agregó validación en rango entero [1, 5] al DTO de satisfacción de la encuesta. |
| UX de borrador local, interceptor de hash y migración DB | `frontend/src/hooks/useAutoSave.js`, `frontend/src/pages/Survey.jsx`, `backend/migrate-mongo-config.js` | Se implementó el hook de autoguardado a LocalStorage cada 30s, la vista estática 'Esta encuesta ya fue respondida' ante hashes de encuesta inválidos/expirados y el archivo base para `migrate-mongo`. |
| Error de DNS `storage.techhelp.com` al abrir/descargar adjuntos | `backend/main.py`, `backend/routes/tickets.py`, `frontend/src/pages/TicketDetail.jsx` | La URL de almacenamiento ficticia no resolvía en un DNS real. Se cambió la estrategia a almacenamiento estático local real montando la carpeta `/uploads` en el backend y sirviendo archivos vía localhost con UUIDs únicos, y se añadió el atributo `download` a los enlaces en el frontend para descargas nativas del navegador. |
| `ReferenceError: userName is not defined` | `frontend/src/layouts/DashboardLayout.jsx` | El componente de la Topbar fallaba al inicializarse porque la variable `userName` no estaba desestructurada desde `useAuthStore`. Se solucionó importando y desestructurando correctamente la variable para evitar pantallas grises inesperadas. |
| Asimetría física del botón de refresco manual | `frontend/src/pages/Organizations.jsx`, `frontend/src/pages/Technicians.jsx`, `frontend/src/pages/Audit.jsx` | El botón de refresco quedaba de menor altura que la barra inteligente de búsqueda. Se resolvió homogenizando las alturas a valores fijos (`h-10` en Organizations, `w-8 h-8` en Technicians y `w-9 h-9` en Audit) y encapsulándolos en contenedores flex con alineación pixel-perfect. |

---

### ## Paso 10 — Infraestructura Docker: Corrección y Preparación para Atlas
**Fecha:** Julio 2026

#### Qué se construyó / corrigió

| Artefacto | Descripción |
| :--- | :--- |
| `backend/Dockerfile` | Se limpió el Dockerfile: se añadió creación explícita del directorio `/app/uploads`, se especificó `--workers 1` en uvicorn y se mejoraron los comentarios. |
| `backend/.dockerignore` | **Nuevo.** Excluye `venv/`, `__pycache__/`, `*.pyc`, `tests/`, `.env` y `*.log` del contexto de build. Reduce el tamaño del contexto enviado al daemon de Docker, acelerando rebuilds. |
| `docker-compose.yml` | Se eliminó el atributo `version` obsoleto (que generaba un warning). Se añadió **healthcheck** en el contenedor MongoDB (`mongosh --eval "db.adminCommand('ping')"`), de modo que el backend espera a que Mongo esté listo antes de arrancar (`condition: service_healthy`). Se agregó un volumen `uploads_data` para persistir archivos adjuntos. Se parametrizaron las variables sensibles para leerlas de `.env`. |
| `docker-compose.atlas.yml` | **Nuevo.** Compose de **producción** que levanta únicamente el contenedor del backend. Lee las variables desde `.env.atlas`. No incluye contenedor MongoDB local. |
| `.env.atlas` | **Nuevo.** Template de variables de entorno para Atlas con el formato correcto del Connection String. Está en `.gitignore` para que nunca se suba a Git. |
| `.gitignore` | Se añadieron `.env.atlas` y `uploads/` a la lista de exclusiones. |

#### Decisiones Técnicas Clave

1. **Healthcheck en MongoDB:** Sin el healthcheck, el backend arrancaba antes que MongoDB estuviera listo, causando fallos en los índices de inicio (`create_indexes()`). Con `condition: service_healthy`, Docker Compose garantiza el orden correcto de arranque.
2. **Separación local vs. Atlas:** Se usa `docker-compose.yml` para desarrollo (MongoDB en contenedor) y `docker-compose.atlas.yml` para producción (solo backend, MongoDB en la nube). Esto evita tener que modificar el compose principal al desplegar.
3. **`.dockerignore` crítico:** El directorio `venv/` pesaba ~300MB y se estaba incluyendo en el contexto de build. Con `.dockerignore` el contexto pasa de ~330KB a ~7KB, reduciendo el tiempo de build drásticamente.
4. **Volumen `uploads_data`:** Los adjuntos subidos por los usuarios se persisten en un volumen nombrado de Docker, evitando que se pierdan al recrear el contenedor del backend.

#### Comandos del paso

```bash
# Verificar que todo está corriendo correctamente
docker ps
# Esperado:
# techhelp_backend   Up X seconds             0.0.0.0:8000->8000/tcp
# techhelp_mongodb   Up X seconds (healthy)   0.0.0.0:27017->27017/tcp

# Probar el healthcheck del API
curl http://localhost:8000/
# Esperado: {"status":"healthy","service":"TechHelp Backend"}

# Ver Swagger UI
# → Abrir en navegador: http://localhost:8000/docs

# Para Atlas: editar .env.atlas y luego:
docker-compose -f docker-compose.atlas.yml up --build -d
```

#### Estado del Docker tras este paso
- ✅ `docker-compose up --build -d` funciona sin errores
- ✅ Backend arranca solo cuando MongoDB está `healthy`
- ✅ API responde en `http://localhost:8000/`
- ✅ Swagger disponible en `http://localhost:8000/docs`
- ✅ Preparado para despliegue en Atlas con `docker-compose.atlas.yml`

---
