# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Dependencias del sistema necesarias para compilar paquetes nativos
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar solo requirements primero para aprovechar la cache de Docker
COPY requirements.txt .

# Instalar en directorio separado para copiarlo al stage final
RUN pip install --upgrade pip \
    && pip install --prefix=/install --no-cache-dir -r requirements.txt


# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Librerías de sistema mínimas para runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copiar paquetes instalados desde el builder
COPY --from=builder /install /usr/local

# Copiar código fuente
COPY app/         ./app/
COPY data/        ./data/
COPY tests/       ./tests/

# Directorios que se montarán como volúmenes en compose
RUN mkdir -p chroma logs

# Usuario no-root por seguridad
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

# Puerto de la aplicación
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/').raise_for_status()"

# Comando de inicio
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
