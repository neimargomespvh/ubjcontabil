-- =========================================================
-- ERP Contábil — Schema completo (init Docker / fresh install)
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

-- erp.empresa
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

-- erp.conta_contabil
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

-- erp.sped_registro
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

-- sync.sync_outbox (com empresa_id desde o início)
CREATE TABLE IF NOT EXISTS sync.sync_outbox (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id      TEXT NOT NULL DEFAULT 'legacy',
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
CREATE UNIQUE INDEX IF NOT EXISTS uq_outbox_pendente
    ON sync.sync_outbox (empresa_id, entidade, registro_id)
    WHERE sincronizado_em IS NULL;

-- sync.watermark
CREATE TABLE IF NOT EXISTS sync.watermark (
    empresa_id     TEXT NOT NULL,
    entidade       TEXT NOT NULL,
    ultima_posicao TIMESTAMPTZ NOT NULL,
    atualizado_em  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (empresa_id, entidade)
);

-- sync.sync_dlq
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

-- erp.documento_fiscal (C100)
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

-- erp.documento_item (C170)
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

-- migracao.usuario (painel Admin com roles)
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
