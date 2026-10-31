-- =========================================================
-- Stage 6 — Usuários do painel com roles
-- Rodar:  psql -d erp_contabil -f ddl/schema_stage6_usuarios.sql
-- =========================================================

CREATE TABLE IF NOT EXISTS migracao.usuario (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username        TEXT NOT NULL,
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('admin', 'operador', 'leitura')),
    nome            TEXT,
    ativo           BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT now(),
    ultimo_login    TIMESTAMPTZ,
    CONSTRAINT uq_usuario_username UNIQUE (username)
);
CREATE INDEX IF NOT EXISTS ix_usuario_ativo ON migracao.usuario (ativo) WHERE ativo = TRUE;
