#!/usr/bin/env bash
# =============================================================================
# ERP Contábil — Migracao
# Script completo: verifica, corrige, sobe e abre o sistema
#
# Uso:
#   ./verificar_e_abrir.sh
#   PORT=8000 DB_HOST_PORT=5433 ./verificar_e_abrir.sh
#   ./verificar_e_abrir.sh --port 8000 --db-port 5433
# =============================================================================
set -euo pipefail

# --- raiz do projeto (funciona se o script estiver na raiz OU em scripts/) ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/docker-compose.yml" ] || [ -f "$SCRIPT_DIR/compose.yml" ]; then
  ROOT="$SCRIPT_DIR"
else
  ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
fi
cd "$ROOT"

# --- cores ---
RED=$'\033[0;31m'
GRN=$'\033[0;32m'
YLW=$'\033[0;33m'
BLU=$'\033[0;34m'
CYN=$'\033[0;36m'
RST=$'\033[0m'
BOLD=$'\033[1m'

ok()   { echo "${GRN}✓${RST} $*"; }
warn() { echo "${YLW}!${RST} $*"; }
err()  { echo "${RED}✗${RST} $*"; }
info() { echo "${BLU}→${RST} $*"; }
step() { echo; echo "${CYN}${BOLD}==>${RST} ${BOLD}$*${RST}"; }

# --- portas (padrão + CLI) ---
ADMIN_PORT="${PORT:-8000}"
DB_HOST_PORT="${DB_HOST_PORT:-5433}"

while [ $# -gt 0 ]; do
  case "$1" in
    --port|-p)
      ADMIN_PORT="${2:-}"
      shift 2 || { err "--port exige valor"; exit 1; }
      ;;
    --db-port)
      DB_HOST_PORT="${2:-}"
      shift 2 || { err "--db-port exige valor"; exit 1; }
      ;;
    --help|-h)
      cat <<EOF
Uso: $0 [opções]

Opções:
  --port, -p PORT     Porta HTTP do painel Admin (padrão: 8000)
  --db-port PORT      Porta do Postgres no HOST (padrão: 5433)
  --help, -h          Esta ajuda

Variáveis de ambiente equivalentes:
  PORT=8000 DB_HOST_PORT=5433 $0
EOF
      exit 0
      ;;
    *)
      err "Opção desconhecida: $1 (use --help)"
      exit 1
      ;;
  esac
done

# valida números de porta
for pair in "ADMIN_PORT:$ADMIN_PORT" "DB_HOST_PORT:$DB_HOST_PORT"; do
  name="${pair%%:*}"
  val="${pair#*:}"
  if ! [[ "$val" =~ ^[0-9]+$ ]] || [ "$val" -lt 1 ] || [ "$val" -gt 65535 ]; then
    err "$name inválida: $val"
    exit 1
  fi
done

echo
echo "${BOLD}ERP Contábil — Migracao — verificação e abertura${RST}"
echo "  Projeto : $ROOT"
echo "  Admin   : http://localhost:${ADMIN_PORT}"
echo "  Postgres: localhost:${DB_HOST_PORT} → container:5432"
echo

# =============================================================================
step "1/8 — Pré-requisitos"
# =============================================================================
if ! command -v docker >/dev/null 2>&1; then
  err "Docker não encontrado. Instale: https://docs.docker.com/get-docker/"
  exit 1
fi
ok "Docker: $(docker --version | head -1)"

if ! docker info >/dev/null 2>&1; then
  err "Docker daemon não está rodando"
  exit 1
fi
ok "Docker daemon ativo"

if ! docker compose version >/dev/null 2>&1; then
  err "Plugin 'docker compose' não disponível"
  exit 1
fi
ok "docker compose: $(docker compose version --short 2>/dev/null || echo ok)"

if [ ! -f docker-compose.yml ] && [ ! -f compose.yml ]; then
  err "docker-compose.yml não encontrado em $ROOT"
  exit 1
fi
ok "compose file presente"

command -v curl >/dev/null 2>&1 || { err "curl é necessário"; exit 1; }
ok "curl disponível"

# =============================================================================
step "2/8 — Arquivo .env"
# =============================================================================
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    cp .env.example .env
    warn "Criado .env a partir de .env.example"
  else
    cat > .env <<EOF
ERP_DATABASE_URL=postgresql://erp:erp_secret@db:5432/erp_contabil
JWT_SECRET=change-me-to-a-long-random-string-at-least-32-chars
JWT_EXPIRE_MINUTES=480
ADMIN_USER=admin
ADMIN_PASSWORD=change-me-strong-password
MIGRACAO_UPLOAD_DIR=/app/uploads
MIGRACAO_LOG=/app/logs/migracao_erros.log
EOF
    warn "Criado .env mínimo"
  fi
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

ENV_CHANGED=0

# ADMIN_USER
if [ -z "${ADMIN_USER:-}" ]; then
  ADMIN_USER=admin
  if grep -q '^ADMIN_USER=' .env; then
    sed -i 's|^ADMIN_USER=.*|ADMIN_USER=admin|' .env
  else
    echo "ADMIN_USER=admin" >> .env
  fi
  ENV_CHANGED=1
  warn "ADMIN_USER definido como admin"
fi

# ADMIN_PASSWORD
if [ -z "${ADMIN_PASSWORD:-}" ] || [ "${ADMIN_PASSWORD}" = "change-me-strong-password" ]; then
  NEW_PASS="$(openssl rand -base64 12 2>/dev/null | tr -d '/+=' | head -c 16 || echo "Admin$(date +%s | tail -c 8)")"
  if grep -q '^ADMIN_PASSWORD=' .env; then
    sed -i "s|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD=${NEW_PASS}|" .env
  else
    echo "ADMIN_PASSWORD=${NEW_PASS}" >> .env
  fi
  ADMIN_PASSWORD="$NEW_PASS"
  ENV_CHANGED=1
  warn "ADMIN_PASSWORD gerada: ${ADMIN_PASSWORD}"
fi

# JWT_SECRET (>=32, não pode ser um JWT de exemplo)
if [ -z "${JWT_SECRET:-}" ] || [ "${#JWT_SECRET}" -lt 32 ] || [[ "${JWT_SECRET}" == eyJ* ]]; then
  NEW_JWT="$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | od -An -tx1 | tr -d ' \n' | head -c 64)"
  if grep -q '^JWT_SECRET=' .env; then
    sed -i "s|^JWT_SECRET=.*|JWT_SECRET=${NEW_JWT}|" .env
  else
    echo "JWT_SECRET=${NEW_JWT}" >> .env
  fi
  JWT_SECRET="$NEW_JWT"
  ENV_CHANGED=1
  warn "JWT_SECRET regenerado (${#JWT_SECRET} chars)"
fi

# Garante URL interna do compose (host 'db', não localhost)
if grep -qE '^ERP_DATABASE_URL=.*localhost' .env 2>/dev/null; then
  sed -i 's|^ERP_DATABASE_URL=.*|ERP_DATABASE_URL=postgresql://erp:erp_secret@db:5432/erp_contabil|' .env
  ENV_CHANGED=1
  warn "ERP_DATABASE_URL ajustada para host interno 'db'"
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

ok "ADMIN_USER=${ADMIN_USER}"
ok "ADMIN_PASSWORD=(${#ADMIN_PASSWORD} chars)"
ok "JWT_SECRET=(${#JWT_SECRET} chars)"
[ "$ENV_CHANGED" -eq 1 ] && ok ".env atualizado" || ok ".env sem mudanças necessárias"

# =============================================================================
step "3/8 — Portas no docker-compose.yml (Admin ${ADMIN_PORT}, DB ${DB_HOST_PORT})"
# =============================================================================
COMPOSE_FILE="docker-compose.yml"
[ -f compose.yml ] && [ ! -f docker-compose.yml ] && COMPOSE_FILE="compose.yml"

# Backup único por execução
BAK="${COMPOSE_FILE}.bak.$(date +%Y%m%d%H%M%S)"
cp "$COMPOSE_FILE" "$BAK"
ok "Backup: $BAK"

# --- Postgres host port ---
# Aceita "5432:5432", '5432:5432', 5432:5432 e qualquer NNNN:5432
if grep -qE '[[:space:]]*[\"'\'']?[0-9]+:5432[\"'\'']?' "$COMPOSE_FILE"; then
  sed -i -E "s/([\"']?)[0-9]+:5432([\"']?)/\"${DB_HOST_PORT}:5432\"/g" "$COMPOSE_FILE"
  ok "Postgres no host: ${DB_HOST_PORT} → container 5432"
else
  warn "Não achei mapeamento *:5432 — confira o serviço db manualmente"
fi

# --- Admin HTTP port (serviço admin, porta 8000 do container) ---
if grep -qE '[[:space:]]*[\"'\'']?[0-9]+:8000[\"'\'']?' "$COMPOSE_FILE"; then
  sed -i -E "s/([\"']?)[0-9]+:8000([\"']?)/\"${ADMIN_PORT}:8000\"/g" "$COMPOSE_FILE"
  ok "Admin no host: ${ADMIN_PORT} → container 8000"
else
  warn "Não achei mapeamento *:8000 — confira o serviço admin manualmente"
fi

# Mostra trechos relevantes
info "Trechos de ports no compose:"
grep -nE 'ports:|[0-9]+:(5432|8000)' "$COMPOSE_FILE" | head -20 || true

# Conflito no host?
port_in_use() {
  local p="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -tln 2>/dev/null | grep -qE ":${p}\\b" && return 0
  fi
  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1 && return 0
  fi
  return 1
}

if port_in_use "$DB_HOST_PORT"; then
  # se a própria stack antiga estiver usando, down resolve; senão avisa
  warn "Porta ${DB_HOST_PORT} parece em uso no host — será tentado docker compose down antes do up"
fi
if port_in_use "$ADMIN_PORT"; then
  warn "Porta ${ADMIN_PORT} parece em uso no host — será tentado docker compose down antes do up"
fi

# =============================================================================
step "4/8 — Subir containers"
# =============================================================================
info "docker compose down…"
docker compose down 2>/dev/null || true

info "docker compose up -d --build…"
if ! docker compose up -d --build; then
  err "Falha no compose up"
  docker compose ps -a || true
  docker compose logs --tail=40 db || true
  docker compose logs --tail=40 admin || true
  exit 1
fi
ok "Compose up solicitado"

# =============================================================================
step "5/8 — Aguardar Postgres (localhost:${DB_HOST_PORT})"
# =============================================================================
DB_READY=0
for i in $(seq 1 40); do
  if docker compose exec -T db pg_isready -U erp -d erp_contabil >/dev/null 2>&1; then
    DB_READY=1
    break
  fi
  STATUS="$(docker compose ps db --format '{{.Status}}' 2>/dev/null || true)"
  if echo "$STATUS" | grep -qiE 'exit|dead'; then
    err "Container db encerrou: $STATUS"
    docker compose logs --tail=50 db
    exit 1
  fi
  sleep 3
done

if [ "$DB_READY" -ne 1 ]; then
  err "Timeout aguardando Postgres"
  docker compose ps -a
  docker compose logs --tail=50 db
  exit 1
fi
ok "Postgres healthy/pronto"

# =============================================================================
step "6/8 — Schema (init + usuarios + movimento)"
# =============================================================================
run_sql() {
  docker compose exec -T db psql -U erp -d erp_contabil -v ON_ERROR_STOP=1 "$@"
}

table_exists() {
  local schema="$1" table="$2"
  run_sql -tAc "SELECT 1 FROM information_schema.tables WHERE table_schema='${schema}' AND table_name='${table}'" 2>/dev/null | grep -q 1
}

if ! table_exists migracao job; then
  warn "Schema base ausente — aplicando ddl/init.sql"
  if [ -f ddl/init.sql ]; then
    run_sql < ddl/init.sql
    ok "init.sql aplicado"
  else
    err "ddl/init.sql não encontrado"
    exit 1
  fi
else
  ok "Schema base (migracao.job) presente"
fi

if ! table_exists migracao usuario; then
  warn "migracao.usuario ausente"
  if [ -f ddl/schema_stage6_usuarios.sql ]; then
    run_sql < ddl/schema_stage6_usuarios.sql
    ok "schema_stage6_usuarios.sql aplicado"
  elif [ -f ddl/init.sql ]; then
    run_sql < ddl/init.sql || true
    table_exists migracao usuario && ok "usuario criada via init.sql" || warn "usuario ainda ausente"
  else
    warn "Sem DDL de usuários"
  fi
else
  ok "migracao.usuario presente"
fi

if ! table_exists erp documento_fiscal; then
  if [ -f ddl/schema_stage5_movimento.sql ]; then
    warn "documento_fiscal ausente — aplicando stage 5"
    run_sql < ddl/schema_stage5_movimento.sql || true
    table_exists erp documento_fiscal && ok "documento_fiscal OK" || warn "stage 5 parcial"
  fi
else
  ok "erp.documento_fiscal presente"
fi

# Contagem de usuários
USER_COUNT="$(run_sql -tAc 'SELECT COUNT(*) FROM migracao.usuario' 2>/dev/null | tr -d '[:space:]' || echo 0)"
info "Usuários na base: ${USER_COUNT:-0}"

# =============================================================================
step "7/8 — Admin na porta ${ADMIN_PORT}"
# =============================================================================
info "Recriando admin (aplica .env + bootstrap de usuário)…"
docker compose up -d --force-recreate admin

ADMIN_READY=0
for i in $(seq 1 40); do
  if curl -fsS "http://127.0.0.1:${ADMIN_PORT}/api/migracao/health" >/dev/null 2>&1; then
    ADMIN_READY=1
    break
  fi
  sleep 2
done

if [ "$ADMIN_READY" -ne 1 ]; then
  err "Admin não respondeu em http://127.0.0.1:${ADMIN_PORT}"
  docker compose ps -a
  docker compose logs --tail=60 admin
  exit 1
fi

HEALTH="$(curl -fsS "http://127.0.0.1:${ADMIN_PORT}/api/migracao/health" || true)"
ok "Health: ${HEALTH}"

info "Testando login (${ADMIN_USER})…"
LOGIN_RESP="$(curl -sS -u "${ADMIN_USER}:${ADMIN_PASSWORD}" \
  -X POST "http://127.0.0.1:${ADMIN_PORT}/api/auth/login" || true)"

if ! echo "$LOGIN_RESP" | grep -q access_token; then
  warn "Login falhou na 1ª tentativa — recriando admin e aguardando bootstrap"
  docker compose logs --tail=30 admin || true
  docker compose up -d --force-recreate admin
  sleep 8
  LOGIN_RESP="$(curl -sS -u "${ADMIN_USER}:${ADMIN_PASSWORD}" \
    -X POST "http://127.0.0.1:${ADMIN_PORT}/api/auth/login" || true)"
fi

if ! echo "$LOGIN_RESP" | grep -q access_token; then
  err "Não foi possível autenticar"
  err "Resposta: ${LOGIN_RESP}"
  err "Confira ADMIN_USER/ADMIN_PASSWORD no .env"
  docker compose logs --tail=50 admin
  exit 1
fi
ok "Login OK"

TOKEN=""
if command -v python3 >/dev/null 2>&1; then
  TOKEN="$(echo "$LOGIN_RESP" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("access_token",""))' 2>/dev/null || true)"
fi

# =============================================================================
step "8/8 — Abrir o sistema"
# =============================================================================
URL="http://localhost:${ADMIN_PORT}/admin/utilitarios/migracao"
URL_HEALTH="http://localhost:${ADMIN_PORT}/api/migracao/health"
URL_BASIC="http://${ADMIN_USER}:${ADMIN_PASSWORD}@localhost:${ADMIN_PORT}/admin/utilitarios/migracao"

echo
echo "=============================================="
echo "  ${BOLD}ERP Contábil — Migracao pronto${RST}"
echo "=============================================="
echo "  Painel:     ${URL}"
echo "  Health:     ${URL_HEALTH}"
echo "  API login:  http://localhost:${ADMIN_PORT}/api/auth/login"
echo "  Usuário:    ${ADMIN_USER}"
echo "  Senha:      ${ADMIN_PASSWORD}"
echo "  Postgres:   localhost:${DB_HOST_PORT} (user=erp db=erp_contabil)"
echo "=============================================="
echo

open_url() {
  local u="$1"
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$u" >/dev/null 2>&1 &
    return 0
  fi
  if command -v gio >/dev/null 2>&1; then
    gio open "$u" >/dev/null 2>&1 &
    return 0
  fi
  if command -v sensible-browser >/dev/null 2>&1; then
    sensible-browser "$u" >/dev/null 2>&1 &
    return 0
  fi
  if command -v firefox >/dev/null 2>&1; then
    firefox "$u" >/dev/null 2>&1 &
    return 0
  fi
  if command -v google-chrome >/dev/null 2>&1; then
    google-chrome "$u" >/dev/null 2>&1 &
    return 0
  fi
  if command -v chromium-browser >/dev/null 2>&1; then
    chromium-browser "$u" >/dev/null 2>&1 &
    return 0
  fi
  if command -v chromium >/dev/null 2>&1; then
    chromium "$u" >/dev/null 2>&1 &
    return 0
  fi
  return 1
}

info "Abrindo navegador…"
if open_url "$URL_BASIC"; then
  ok "Navegador aberto (Basic na URL)"
elif open_url "$URL"; then
  ok "Navegador aberto — informe usuário/senha se pedir"
else
  warn "Não foi possível abrir o navegador automaticamente"
  echo "  Abra: ${URL}"
  echo "  Login: ${ADMIN_USER} / ${ADMIN_PASSWORD}"
fi

echo
ok "Concluído."
echo "  Dica: ./verificar_e_abrir.sh --port ${ADMIN_PORT} --db-port ${DB_HOST_PORT}"
