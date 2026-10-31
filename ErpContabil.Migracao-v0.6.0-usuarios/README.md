# ERP Contábil — Módulo de Migração

**Versão 0.5.0** — Production-ready

Ferramenta de migração de dados contábeis de sistemas legados brasileiros (**Fortes Tecnologia** / SQL Server, **Tron** / Firebird e arquivos **SPED** .txt) para o ERP Contábil em PostgreSQL.

## Arquitetura

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│  Extract    │────▶│  Transform   │────▶│    Load     │────▶│  Outbox +    │
│ (streamed)  │     │ (validate)   │     │ (COPY bulk) │     │  SyncWorker  │
└─────────────┘     └──────────────┘     └─────────────┘     └──────────────┘
   Fortes / Tron / SPED          CPF/CNPJ + De-Para              Delta / DLQ
```

- **Domain**: entidades imutáveis, Protocols (`IEntityExtractor`, `IEntityTransformer`, `IEntityLoader`, `IMigrationOrchestrator`).
- **Extract**: keyset pagination + `WITH (NOLOCK)` (SQL Server), leitura streaming de SPED, Firebird.
- **Transform**: normalizers + validadores fiscais brasileiros (CPF/CNPJ com dígito verificador).
- **Load**: `psycopg` COPY binary + fallback row-by-row + escrita atômica no outbox.
- **Sync**: worker separado com batch, retry, DLQ e watermark.
- **Admin**: FastAPI + JWT (com fallback Basic) + auditoria de ações.

## Requisitos

- Python ≥ 3.11
- PostgreSQL ≥ 14 (recomendado 16)
- Acesso de leitura ao SQL Server da Fortes (ou arquivos SPED / Firebird)

## Quick start (Docker)

```bash
cp .env.example .env
# Edite JWT_SECRET e ADMIN_PASSWORD (obrigatório)

docker compose up -d --build

# Painel: http://localhost:8000/admin/utilitarios/migracao
# Health:  http://localhost:8000/api/migracao/health
```

Login:
1. `POST /api/auth/login` com Basic Auth → recebe JWT.
2. Use `Authorization: Bearer <token>` nas demais rotas.

Ou continue usando Basic Auth diretamente (compatibilidade).

## Desenvolvimento local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Configure ERP_DATABASE_URL, JWT_SECRET, ADMIN_PASSWORD

# Schema
psql "$ERP_DATABASE_URL" -f ddl/init.sql

# Painel
./scripts/run_admin.sh

# Worker de sync (outro terminal)
python scripts/run_sync_worker.py
```

## Configuração (.env)

| Variável | Descrição | Obrigatório |
|----------|-----------|-------------|
| `ERP_DATABASE_URL` | Connection string Postgres | Sim |
| `JWT_SECRET` | Segredo JWT (≥32 chars) | Sim (prod) |
| `ADMIN_USER` / `ADMIN_PASSWORD` | Credenciais do painel | Sim |
| `MIGRACAO_UPLOAD_DIR` | Diretório de uploads SPED | Não |
| `DELTA_BASE_URL` / `DELTA_API_KEY` | Endpoint do sincronizador Delta | Não |
| `SYNC_BATCH_SIZE` / `SYNC_POLL_INTERVAL_S` | Tuning do worker | Não |

## API principal

| Método | Rota | Auth | Descrição |
|--------|------|------|-----------|
| GET | `/api/migracao/health` | — | Healthcheck |
| POST | `/api/auth/login` | Basic | Emite JWT |
| POST | `/api/migracao/fortes/testar` | JWT/Basic | Testa conexão Fortes |
| POST | `/api/migracao/fortes/iniciar` | JWT/Basic | Inicia job Fortes |
| POST | `/api/migracao/arquivos/upload` | JWT/Basic | Upload SPED/XML |
| POST | `/api/migracao/arquivos/iniciar` | JWT/Basic | Job a partir de arquivos |
| GET | `/api/migracao/status/{job_id}` | JWT/Basic | Progresso do job |
| GET | `/api/migracao/jobs` | JWT/Basic | Lista jobs |
| GET | `/api/migracao/sync/status` | JWT/Basic | Status do outbox/DLQ |

## Testes e qualidade

```bash
pytest -v
pytest -m integration   # exige ERP_TEST_DATABASE_URL
mypy src/
ruff check src/
```

## Estrutura do repositório

```
src/
  domain/          # entidades, contracts, enums
  extract/         # Fortes, Tron, SPED, shared
  transform/       # mappings, validators, normalizers, SPED
  load/            # bulk + fallback + outbox
  infrastructure/  # orchestrator, sync, resilience, logging
  web/             # FastAPI admin + JWT + audit
ddl/               # schema SQL (init.sql = completo)
scripts/           # run_admin, run_sync_worker, demos, setup_db
configs/           # mapas de configuração (ex.: Tron)
tools/             # scripts históricos de stage (não usados em prod)
tests/
```

## Runbook operacional

### Subir ambiente
```bash
docker compose up -d
docker compose logs -f admin
```

### Rodar migração Fortes
1. Acesse o painel ou use a API.
2. Teste conexão (`/fortes/testar`).
3. Inicie job com as etapas desejadas (`empresa`, `plano_contas`, `participante`).
4. Acompanhe `/status/{job_id}`.

### Monitorar sync
```bash
curl -u admin:$ADMIN_PASSWORD http://localhost:8000/api/migracao/sync/status
```

### Logs de auditoria
Procure por linhas `AUDIT user=... action=...` nos logs do container `admin`.

### Backup / restore
O volume `pgdata` contém o Postgres. Use `pg_dump` / `pg_restore` normalmente.

## SPED — cobertura de registros

| Registro | Entidade ERP | Observação |
|----------|--------------|------------|
| 0150 | `erp.participante` | Cadastro de participantes |
| 0500 | `erp.conta_contabil` | Plano de contas |
| C100 | `erp.documento_fiscal` | Cabeçalho NF / documento |
| C170 | `erp.documento_item` | Itens vinculados ao C100 pai |
| * | `erp.sped_registro` | Auditoria bruta (pipeline não-estruturado) |

O pipeline **estruturado** (`/api/migracao/arquivos/estruturado`) processa 0150 → 0500 → movimentos (C100+C170 com vínculo documento→itens preservado via leitura sequencial).


## Usuários e roles

Na primeira subida, se a tabela `migracao.usuario` estiver vazia, o sistema cria automaticamente um usuário **admin** com `ADMIN_USER` / `ADMIN_PASSWORD` do `.env`.

| Role | Permissões |
|------|------------|
| `admin` | Tudo + gestão de usuários |
| `operador` | Iniciar migrações, upload, testar conexões |
| `leitura` | Ver jobs, status, painel (somente leitura) |

### API de usuários (somente admin)

```bash
# listar
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/usuarios

# criar operador
curl -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"username":"ops","password":"senha-segura-8+","role":"operador","nome":"Operador"}' \
  http://localhost:8000/api/usuarios

# alterar role / senha / desativar
curl -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"role":"leitura","ativo":true}' \
  http://localhost:8000/api/usuarios/{id}
```

Base existente (sem recriar volume Docker):

```bash
psql "$ERP_DATABASE_URL" -f ddl/schema_stage6_usuarios.sql
docker compose up -d --force-recreate admin
```


## Limitações conhecidas / roadmap

- Mapeamento Fortes ainda depende de nomes de tabela/coluna conhecidos (schema discovery existe, mas o caminho feliz é fixo).
- Tron (Firebird) implementado, porém menos batido em produção que Fortes.
- SPED: bloco C (documentos) coberto (C100/C170); outros blocos (D=serviços, C190 consolidado, etc.) podem ser estendidos sob demanda.
- Auth: JWT + Basic. Para ambientes multi-usuário considere OIDC / SSO.

## Licença

Uso interno — ERP Contábil.
