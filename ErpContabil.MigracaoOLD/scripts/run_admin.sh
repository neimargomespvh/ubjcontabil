#!/usr/bin/env bash
# Sobe o painel Admin com uvicorn.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v uvicorn >/dev/null 2>&1; then
    echo "❌ uvicorn não encontrado no PATH." >&2
    echo "   Rode: pip install -r requirements-web.txt" >&2
    exit 1
fi

if [ -z "${ADMIN_PASSWORD:-}" ]; then
    echo "⚠️  ADMIN_PASSWORD não definida. O painel vai recusar login (falha fechada)." >&2
    echo "   Defina: export ADMIN_PASSWORD='senha-forte-aqui'" >&2
fi

exec uvicorn src.web.app:app \
    --app-dir . \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --reload
