-- =========================================================
-- Stage 3 — tabelas erp.empresa, erp.conta_contabil, erp.sped_registro
-- Rodar:  psql -d erp_contabil -f ddl/schema_stage3.sql
-- =========================================================

CREATE TABLE IF NOT EXISTS erp.empresa (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id        TEXT NOT NULL,
    codigo_origem     BIGINT NOT NULL,
    origem_sistema    TEXT NOT NULL,
    razao_social      TEXT NOT NULL,
    cnpj              TEXT NOT NULL,
    uf                CHAR(2),
    regime_tributario TEXT,
    criado_em         TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_empresa_origem UNIQUE (empresa_id, origem_sistema, codigo_origem)
);

CREATE TABLE IF NOT EXISTS erp.conta_contabil (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id     TEXT NOT NULL,
    codigo         TEXT NOT NULL,
    nome           TEXT NOT NULL,
    codigo_pai     TEXT,
    natureza       TEXT NOT NULL CHECK (natureza IN ('SINTETICA','ANALITICA')),
    grau           INT  NOT NULL,
    natureza_saldo TEXT CHECK (natureza_saldo IN ('DEVEDORA','CREDORA')),
    criado_em      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_conta_empresa UNIQUE (empresa_id, codigo)
);
CREATE INDEX IF NOT EXISTS ix_conta_pai ON erp.conta_contabil (empresa_id, codigo_pai);

CREATE TABLE IF NOT EXISTS erp.sped_registro (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id   TEXT NOT NULL,
    arquivo      TEXT NOT NULL,
    numero_linha BIGINT NOT NULL,
    codigo       TEXT NOT NULL,
    campos_json  TEXT NOT NULL,
    linha_bruta  TEXT NOT NULL,
    criado_em    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_sped_registro UNIQUE (empresa_id, arquivo, numero_linha)
);
CREATE INDEX IF NOT EXISTS ix_sped_codigo ON erp.sped_registro (empresa_id, codigo);
