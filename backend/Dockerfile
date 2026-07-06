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

# Crear directorio de uploads (adjuntos locales)
RUN mkdir -p /app/uploads

EXPOSE 8000

# Arrancar uvicorn apuntando a backend.main:app
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]