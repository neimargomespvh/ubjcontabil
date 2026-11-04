-- ====================================================================
-- UBJ CONTÁBIL - PROPOSTA DE ARQUITETURA DE BANCO DE DADOS POSTGRESQL
-- Otimizado para Alta Performance, Integridade Contábil e Multitenancy
-- ====================================================================

-- 1. Extensões essenciais
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- 2. Schemas Departamentais para Organização Modular
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS contabil;
CREATE SCHEMA IF NOT EXISTS fiscal;
CREATE SCHEMA IF NOT EXISTS folha;
CREATE SCHEMA IF NOT EXISTS financeiro;

-- --------------------------------------------------------------------
-- TABELA CORE: EMPRESAS / CLIENTES DO ESCRITÓRIO
-- --------------------------------------------------------------------
CREATE TABLE core.empresas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    cnpj VARCHAR(14) NOT NULL,
    razao_social VARCHAR(255) NOT NULL,
    nome_fantasia VARCHAR(255),
    regime_tributario VARCHAR(30) NOT NULL CHECK (regime_tributario IN ('SIMPLES_NACIONAL', 'LUCRO_PRESUMIDO', 'LUCRO_REAL', 'MEI')),
    inscricao_estadual VARCHAR(20),
    inscricao_municipal VARCHAR(20),
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT uq_empresa_cnpj UNIQUE (cnpj)
);
CREATE INDEX idx_empresas_tenant_ativo ON core.empresas(tenant_id, ativo);

-- --------------------------------------------------------------------
-- TABELA CONTÁBIL: PLANO DE CONTAS COM REFERENCIAL RFB (ECD/ECF)
-- --------------------------------------------------------------------
CREATE TABLE contabil.plano_contas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES core.empresas(id) ON DELETE CASCADE,
    codigo_estrutural VARCHAR(30) NOT NULL, -- ex: 1.1.01.01.0001
    codigo_reduzido INTEGER NOT NULL,      -- Digitação rápida no lançamento
    descricao VARCHAR(150) NOT NULL,
    natureza CHAR(1) NOT NULL CHECK (natureza IN ('D', 'C')),
    tipo_conta VARCHAR(10) NOT NULL CHECK (tipo_conta IN ('SINTETICA', 'ANALITICA')),
    nivel SMALLINT NOT NULL CHECK (nivel BETWEEN 1 AND 7),
    codigo_referencial_rfb VARCHAR(30),   -- Para SPED ECD e ECF
    aceita_conciliacao BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT uq_plano_empresa_estrutural UNIQUE (empresa_id, codigo_estrutural),
    CONSTRAINT uq_plano_empresa_reduzido UNIQUE (empresa_id, codigo_reduzido)
);
CREATE INDEX idx_plano_reduzido ON contabil.plano_contas(empresa_id, codigo_reduzido);

-- --------------------------------------------------------------------
-- TABELA CONTÁBIL: LANÇAMENTOS COM PARTICIONAMENTO DECLARATIVO
-- Particionada por intervalo de data (evita gargalo com 10M+ lançamentos)
-- --------------------------------------------------------------------
CREATE TABLE contabil.lancamentos_contabeis (
    id UUID DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES core.empresas(id) ON DELETE CASCADE,
    data_lancamento DATE NOT NULL,
    competencia_ano_mes INTEGER NOT NULL, -- ex: 202610
    numero_lote VARCHAR(50),
    documento_origem VARCHAR(100),
    historico_complemento TEXT,
    total_debito NUMERIC(15,2) NOT NULL CHECK (total_debito >= 0),
    total_credito NUMERIC(15,2) NOT NULL CHECK (total_credito >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'EFETIVADO' CHECK (status IN ('RASCUNHO', 'EFETIVADO', 'ESTORNADO')),
    criado_por UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (id, data_lancamento)
) PARTITION BY RANGE (data_lancamento);

-- Exemplo de partições declarativas (automatizadas via cron/trigger anual)
CREATE TABLE contabil.lancamentos_2025 PARTITION OF contabil.lancamentos_contabeis
    FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');

CREATE TABLE contabil.lancamentos_2026 PARTITION OF contabil.lancamentos_contabeis
    FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');

CREATE TABLE contabil.lancamentos_2027 PARTITION OF contabil.lancamentos_contabeis
    FOR VALUES FROM ('2027-01-01') TO ('2028-01-01');

CREATE INDEX idx_lancamentos_empresa_competencia ON contabil.lancamentos_contabeis(empresa_id, competencia_ano_mes);
CREATE INDEX idx_lancamentos_empresa_data ON contabil.lancamentos_contabeis(empresa_id, data_lancamento DESC);

-- --------------------------------------------------------------------
-- TABELA CONTÁBIL: PARTIDAS (DÉBITO E CRÉDITO MULTIPLO)
-- --------------------------------------------------------------------
CREATE TABLE contabil.partidas_contabeis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lancamento_id UUID NOT NULL,
    data_lancamento DATE NOT NULL,
    conta_id UUID NOT NULL REFERENCES contabil.plano_contas(id),
    tipo CHAR(1) NOT NULL CHECK (tipo IN ('D', 'C')),
    valor NUMERIC(15,2) NOT NULL CHECK (valor > 0),
    centro_custo_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX idx_partidas_lancamento ON contabil.partidas_contabeis(lancamento_id);
CREATE INDEX idx_partidas_conta_data ON contabil.partidas_contabeis(conta_id, data_lancamento);

-- --------------------------------------------------------------------
-- TABELA DE ALTA VELOCIDADE: SALDOS ACUMULADOS MENSAIS (BALANCETE O(1))
-- --------------------------------------------------------------------
CREATE TABLE contabil.saldos_acumulados_mensais (
    empresa_id UUID NOT NULL REFERENCES core.empresas(id) ON DELETE CASCADE,
    conta_id UUID NOT NULL REFERENCES contabil.plano_contas(id) ON DELETE CASCADE,
    ano_mes INTEGER NOT NULL, -- YYYYMM (ex: 202610)
    saldo_inicial NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    total_debitos NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    total_creditos NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    saldo_final NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    fechado BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (empresa_id, conta_id, ano_mes)
);
CREATE INDEX idx_saldos_busca_balancete ON contabil.saldos_acumulados_mensais(empresa_id, ano_mes);

-- --------------------------------------------------------------------
-- TRIGGER DE CONFERÊNCIA RIGOROSA: PARTIDAS DOBRADAS (DÉBITO == CRÉDITO)
-- --------------------------------------------------------------------
CREATE OR REPLACE FUNCTION contabil.fn_valida_partidas_dobradas()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.total_debito <> NEW.total_credito THEN
        RAISE EXCEPTION 'Violação do Princípio das Partidas Dobradas: Débito (R$ %) diferente do Crédito (R$ %)', 
            NEW.total_debito, NEW.total_credito;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_valida_partidas_dobradas
BEFORE INSERT OR UPDATE ON contabil.lancamentos_contabeis
FOR EACH ROW EXECUTE FUNCTION contabil.fn_valida_partidas_dobradas();
