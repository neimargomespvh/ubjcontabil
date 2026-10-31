-- =========================================================
-- ERP Contábil — Schema mínimo para o migrador
-- Rodar:  psql -d erp_contabil -f ddl/schema.sql
-- =========================================================
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS erp;
CREATE SCHEMA IF NOT EXISTS sync;
CREATE SCHEMA IF NOT EXISTS migracao;

-- erp.participante
CREATE TABLE IF NOT EXISTS erp.participante (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id         TEXT NOT NULL,
    codigo_origem      BIGINT NOT NULL,
    origem_sistema     TEXT NOT NULL,
    razao_social       TEXT NOT NULL,
    nome_fantasia      TEXT,
    documento          TEXT NOT NULL,
    tipo_pessoa        TEXT NOT NULL CHECK (tipo_pessoa IN ('FISICA','JURIDICA')),
    inscricao_estadual TEXT,
    municipio          TEXT,
    uf                 CHAR(2),
    cep                TEXT,
    email              TEXT,
    telefone           TEXT,
    criado_em          TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_participante_origem UNIQUE (empresa_id, origem_sistema, codigo_origem)
);
CREATE INDEX IF NOT EXISTS ix_participante_atualizado_em
    ON erp.participante (atualizado_em);

-- sync.sync_outbox
CREATE TABLE IF NOT EXISTS sync.sync_outbox (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entidade        TEXT NOT NULL,
    registro_id     TEXT NOT NULL,
    operacao        TEXT NOT NULL CHECK (operacao IN ('UPSERT','DELETE')),
    tentativas      INT NOT NULL DEFAULT 0,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT now(),
    agendado_para   TIMESTAMPTZ NOT NULL DEFAULT now(),
    sincronizado_em TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_outbox_pendentes
    ON sync.sync_outbox (agendado_para) WHERE sincronizado_em IS NULL;

-- sync.watermark
CREATE TABLE IF NOT EXISTS sync.watermark (
    empresa_id     TEXT NOT NULL,
    entidade       TEXT NOT NULL,
    ultima_posicao TIMESTAMPTZ NOT NULL,
    atualizado_em  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (empresa_id, entidade)
);

-- migracao.erro
CREATE TABLE IF NOT EXISTS migracao.erro (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entidade    TEXT NOT NULL,
    registro_id TEXT NOT NULL,
    mensagem    TEXT NOT NULL,
    stack       TEXT,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_migracao_erro_entidade
    ON migracao.erro (entidade, criado_em);

-- migracao.job
CREATE TABLE IF NOT EXISTS migracao.job (
    id            UUID PRIMARY KEY,
    origem        TEXT NOT NULL,
    iniciado_em   TIMESTAMPTZ NOT NULL DEFAULT now(),
    finalizado_em TIMESTAMPTZ,
    sucesso       BOOLEAN,
    importados    INT NOT NULL DEFAULT 0,
    erros         INT NOT NULL DEFAULT 0,
    duracao_s     DOUBLE PRECISION NOT NULL DEFAULT 0
);
