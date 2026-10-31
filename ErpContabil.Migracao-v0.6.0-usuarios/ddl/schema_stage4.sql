-- =========================================================
-- Stage 4 — Sync delta (empresa_id + DLQ)
-- Rodar:  psql -d erp_contabil -f ddl/schema_stage4.sql
-- =========================================================

ALTER TABLE sync.sync_outbox
    ADD COLUMN IF NOT EXISTS empresa_id TEXT;

UPDATE sync.sync_outbox SET empresa_id = 'legacy' WHERE empresa_id IS NULL;
ALTER TABLE sync.sync_outbox ALTER COLUMN empresa_id SET NOT NULL;

-- Unicidade: um evento pendente por (empresa, entidade, registro)
CREATE UNIQUE INDEX IF NOT EXISTS uq_outbox_pendente
    ON sync.sync_outbox (empresa_id, entidade, registro_id)
    WHERE sincronizado_em IS NULL;

-- Dead Letter Queue: eventos que esgotaram tentativas
CREATE TABLE IF NOT EXISTS sync.sync_dlq (
    id            UUID PRIMARY KEY,
    empresa_id    TEXT NOT NULL,
    entidade      TEXT NOT NULL,
    operacao      TEXT NOT NULL,
    registro_id   TEXT NOT NULL,
    tentativas    INT NOT NULL,
    erro          TEXT,
    criado_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
    movido_em     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_dlq_entidade ON sync.sync_dlq (entidade, movido_em);
