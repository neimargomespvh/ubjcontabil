-- =========================================================
-- Stage 5 — Documentos fiscais de movimento (C100 / C170)
-- Rodar:  psql -d erp_contabil -f ddl/schema_stage5_movimento.sql
-- =========================================================

CREATE TABLE IF NOT EXISTS erp.documento_fiscal (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id           TEXT NOT NULL,
    codigo_origem        TEXT NOT NULL,
    origem_sistema       TEXT NOT NULL DEFAULT 'SPED',
    chave_nfe            TEXT,
    numero               TEXT NOT NULL,
    serie                TEXT,
    modelo               TEXT NOT NULL,
    data_emissao         TEXT,
    data_entrada_saida   TEXT,
    ind_oper             CHAR(1) NOT NULL,
    ind_emit             CHAR(1) NOT NULL,
    cod_part             TEXT,
    cod_sit              TEXT NOT NULL DEFAULT '00',
    valor_documento      NUMERIC(18,2) NOT NULL DEFAULT 0,
    valor_mercadoria     NUMERIC(18,2) NOT NULL DEFAULT 0,
    valor_desconto       NUMERIC(18,2) NOT NULL DEFAULT 0,
    valor_icms           NUMERIC(18,2) NOT NULL DEFAULT 0,
    valor_ipi            NUMERIC(18,2) NOT NULL DEFAULT 0,
    valor_pis            NUMERIC(18,2) NOT NULL DEFAULT 0,
    valor_cofins         NUMERIC(18,2) NOT NULL DEFAULT 0,
    criado_em            TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_documento_origem UNIQUE (empresa_id, origem_sistema, codigo_origem)
);
CREATE INDEX IF NOT EXISTS ix_documento_chave ON erp.documento_fiscal (chave_nfe)
    WHERE chave_nfe IS NOT NULL AND chave_nfe <> '';
CREATE INDEX IF NOT EXISTS ix_documento_data ON erp.documento_fiscal (empresa_id, data_emissao);
CREATE INDEX IF NOT EXISTS ix_documento_part ON erp.documento_fiscal (empresa_id, cod_part);

CREATE TABLE IF NOT EXISTS erp.documento_item (
    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id                TEXT NOT NULL,
    codigo_origem             TEXT NOT NULL,
    origem_sistema            TEXT NOT NULL DEFAULT 'SPED',
    documento_codigo_origem   TEXT NOT NULL,
    num_item                  INT NOT NULL,
    cod_item                  TEXT NOT NULL,
    descricao                 TEXT,
    quantidade                NUMERIC(18,6) NOT NULL DEFAULT 0,
    unidade                   TEXT,
    valor_item                NUMERIC(18,2) NOT NULL DEFAULT 0,
    valor_desconto            NUMERIC(18,2) NOT NULL DEFAULT 0,
    cfop                      TEXT,
    cst_icms                  TEXT,
    valor_bc_icms             NUMERIC(18,2) NOT NULL DEFAULT 0,
    aliquota_icms             NUMERIC(8,4) NOT NULL DEFAULT 0,
    valor_icms                NUMERIC(18,2) NOT NULL DEFAULT 0,
    criado_em                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_documento_item_origem UNIQUE (empresa_id, origem_sistema, codigo_origem)
);
CREATE INDEX IF NOT EXISTS ix_item_documento
    ON erp.documento_item (empresa_id, documento_codigo_origem);
CREATE INDEX IF NOT EXISTS ix_item_cfop ON erp.documento_item (empresa_id, cfop);
