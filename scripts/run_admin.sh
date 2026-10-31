#!/usr/bin/env bash
# Sobe o painel Admin com uvicorn.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if ! command -v uvicorn >/dev/null 2>&1; then
    echo "❌ uvicorn não encontrado. Rode: pip install -r requirements.txt" >&2
    exit 1
fi

if [ -z "${ADMIN_PASSWORD:-}" ]; then
    echo "⚠️  ADMIN_PASSWORD não definida. O painel vai recusar login." >&2
fi
if [ -z "${JWT_SECRET:-}" ] || [ "${#JWT_SECRET}" -lt 32 ]; then
    echo "⚠️  JWT_SECRET ausente ou curto (<32). Defina no .env" >&2
fi

exec uvicorn src.web.app:app \
    --app-dir . \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --reload
