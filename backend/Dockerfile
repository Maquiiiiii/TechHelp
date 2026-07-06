FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python primero (capa cacheada)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código dentro de un subdirectorio 'backend' para que los imports funcionen
COPY . ./backend/

# PYTHONPATH=/app para que Python encuentre 'backend.*' como módulo
ENV PYTHONPATH=/app

# Crear directorio de uploads (adjuntos locales) con ruta absoluta
RUN mkdir -p /app/uploads

# Railway asigna el puerto dinámicamente mediante la variable PORT.
# No hardcodeamos 8000 aquí; lo leemos en tiempo de ejecución.
EXPOSE 8000

# --proxy-headers es necesario porque Railway usa un reverse proxy (los headers X-Forwarded-* deben propagarse)
# --host 0.0.0.0 es obligatorio para que Railway pueda hacer healthcheck
# El puerto lo inyecta Railway con $PORT (default 8000 si no se define)
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*' --workers 1"]