cd ~/Projetos/UbjContabil
cat > verificar_e_abrir.sh << 'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

RED=$'\033[0;31m'; GRN=$'\033[0;32m'; YLW=$'\033[0;33m'; BLU=$'\033[0;34m'; RST=$'\033[0m'
ok(){ echo "${GRN}✓${RST} $*"; }; warn(){ echo "${YLW}!${RST} $*"; }; err(){ echo "${RED}✗${RST} $*"; }; info(){ echo "${BLU}→${RST} $*"; }

ADMIN_PORT="${PORT:-8000}"
DB_HOST_PORT="${DB_HOST_PORT:-5433}"

info "Verificando Docker…"
command -v docker >/dev/null || { err "Docker não instalado"; exit 1; }
docker info >/dev/null 2>&1 || { err "Docker não está rodando"; exit 1; }
[ -f docker-compose.yml ] || { err "Rode na pasta do projeto (docker-compose.yml)"; exit 1; }
ok "Docker OK"

info "Verificando .env…"
if [ ! -f .env ]; then
  [ -f .env.example ] && cp .env.example .env || cat > .env <<'EOF'
ERP_DATABASE_URL=postgresql://erp:erp_secret@db:5432/erp_contabil
JWT_SECRET=change-me-to-a-long-random-string-at-least-32-chars
JWT_EXPIRE_MINUTES=480
ADMIN_USER=admin
ADMIN_PASSWORD=change-me-strong-password
EOF
  warn "Arquivo .env criado"
fi
set -a; source .env; set +a

if [ -z "${ADMIN_PASSWORD:-}" ] || [ "$ADMIN_PASSWORD" = "change-me-strong-password" ]; then
  NEW_PASS="$(openssl rand -base64 12 2>/dev/null | tr -d '/+=' | head -c 16 || echo AdminTroque123)"
  sed -i "s|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD=${NEW_PASS}|" .env 2>/dev/null || echo "ADMIN_PASSWORD=${NEW_PASS}" >> .env
  ADMIN_PASSWORD="$NEW_PASS"
  warn "ADMIN_PASSWORD gerada: $ADMIN_PASSWORD"
fi
[ -z "${ADMIN_USER:-}" ] && ADMIN_USER=admin && sed -i 's|^ADMIN_USER=.*|ADMIN_USER=admin|' .env 2>/dev/null || true

if [ -z "${JWT_SECRET:-}" ] || [ "${#JWT_SECRET}" -lt 32 ] || [[ "${JWT_SECRET}" == eyJ* ]]; then
  NEW_JWT="$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | od -An -tx1 | tr -d ' \n' | head -c 64)"
  sed -i "s|^JWT_SECRET=.*|JWT_SECRET=${NEW_JWT}|" .env 2>/dev/null || echo "JWT_SECRET=${NEW_JWT}" >> .env
  JWT_SECRET="$NEW_JWT"
  warn "JWT_SECRET regenerado"
fi
set -a; source .env; set +a
ok ".env OK (user=$ADMIN_USER)"

info "Ajustando porta Postgres no host → ${DB_HOST_PORT}…"
if grep -qE '["'\'']?5432:5432["'\'']?' docker-compose.yml; then
  sed -i "s/[\"']\?5432:5432[\"']\?/\"${DB_HOST_PORT}:5432\"/" docker-compose.yml
  ok "Mapeamento: ${DB_HOST_PORT}:5432"
else
  ok "Porta do compose já configurada"
fi

info "Subindo containers…"
docker compose down 2>/dev/null || true
docker compose up -d --build

info "Aguardando Postgres…"
for i in $(seq 1 30); do
  if docker compose exec -T db pg_isready -U erp -d erp_contabil >/dev/null 2>&1; then
    ok "Postgres pronto"; break
  fi
  sleep 3
  [ "$i" -eq 30 ] && { err "Timeout Postgres"; docker compose logs --tail=30 db; exit 1; }
done

info "Verificando schema…"
run_sql(){ docker compose exec -T db psql -U erp -d erp_contabil -v ON_ERROR_STOP=1 "$@"; }

if ! run_sql -tAc "SELECT 1 FROM information_schema.tables WHERE table_schema='migracao' AND table_name='job'" 2>/dev/null | grep -q 1; then
  [ -f ddl/init.sql ] && run_sql < ddl/init.sql && ok "init.sql aplicado" || { err "Sem ddl/init.sql"; exit 1; }
else
  ok "Schema base OK"
fi

if ! run_sql -tAc "SELECT 1 FROM information_schema.tables WHERE table_schema='migracao' AND table_name='usuario'" 2>/dev/null | grep -q 1; then
  if [ -f ddl/schema_stage6_usuarios.sql ]; then
    run_sql < ddl/schema_stage6_usuarios.sql && ok "Tabela usuario criada"
  elif [ -f ddl/init.sql ]; then
    run_sql < ddl/init.sql || true
  else
    warn "Sem DDL de usuarios — login pode falhar até aplicar schema"
  fi
else
  ok "Tabela usuario OK"
fi

info "Recriando admin…"
docker compose up -d --force-recreate admin

info "Aguardando API na porta ${ADMIN_PORT}…"
for i in $(seq 1 30); do
  curl -fsS "http://127.0.0.1:${ADMIN_PORT}/api/migracao/health" >/dev/null 2>&1 && break
  sleep 2
  [ "$i" -eq 30 ] && { err "Admin não subiu"; docker compose logs --tail=40 admin; exit 1; }
done
ok "Health: $(curl -fsS http://127.0.0.1:${ADMIN_PORT}/api/migracao/health)"

info "Testando login…"
LOGIN="$(curl -sS -u "${ADMIN_USER}:${ADMIN_PASSWORD}" -X POST "http://127.0.0.1:${ADMIN_PORT}/api/auth/login" || true)"
if ! echo "$LOGIN" | grep -q access_token; then
  warn "1ª tentativa falhou — recriando admin"
  docker compose up -d --force-recreate admin
  sleep 6
  LOGIN="$(curl -sS -u "${ADMIN_USER}:${ADMIN_PASSWORD}" -X POST "http://127.0.0.1:${ADMIN_PORT}/api/auth/login" || true)"
fi
echo "$LOGIN" | grep -q access_token || { err "Login falhou: $LOGIN"; docker compose logs --tail=40 admin; exit 1; }
ok "Login OK"

URL="http://localhost:${ADMIN_PORT}/admin/utilitarios/migracao"
echo
echo "=============================================="
echo "  Painel:   $URL"
echo "  Health:   http://localhost:${ADMIN_PORT}/api/migracao/health"
echo "  Usuário:  $ADMIN_USER"
echo "  Senha:    $ADMIN_PASSWORD"
echo "  Postgres: localhost:${DB_HOST_PORT}"
echo "=============================================="
echo

info "Abrindo navegador…"
if command -v xdg-open >/dev/null; then xdg-open "$URL" >/dev/null 2>&1 &
elif command -v firefox >/dev/null; then firefox "$URL" >/dev/null 2>&1 &
elif command -v google-chrome >/dev/null; then google-chrome "$URL" >/dev/null 2>&1 &
else warn "Abra manualmente: $URL"
fi
ok "Concluído."
SCRIPT
chmod +x verificar_e_abrir.sh
./verificar_e_abrir.sh