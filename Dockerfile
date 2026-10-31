# syntax=docker/dockerfile:1.6
FROM python:3.12-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependências de sistema para pymssql (FreeTDS) e psycopg
RUN apt-get update && apt-get install -y --no-install-recommends \
        freetds-dev \
        freetds-bin \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY pyproject.toml .
COPY src/ src/
COPY scripts/ scripts/
COPY ddl/ ddl/
COPY configs/ configs/

# Usuário não-root
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/uploads /app/logs \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/migracao/health || exit 1

# Default: painel Admin
CMD ["uvicorn", "src.web.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
