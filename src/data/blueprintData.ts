import { DatabaseTable, PerformancePillar, FeatureProposal, AuditChecklistItem, CodeAnalysisPreset } from '../types';

export const DATABASE_TABLES: DatabaseTable[] = [
  {
    id: 'empresas',
    schema: 'core',
    name: 'empresas',
    description: 'Cadastro central de empresas/clientes contábeis, filiais, regimes tributários e configurações fiscais.',
    columns: [
      { name: 'id', type: 'UUID', constraints: 'DEFAULT gen_random_uuid()', isPrimary: true, description: 'Chave primária imutável' },
      { name: 'tenant_id', type: 'UUID', constraints: 'NOT NULL', description: 'Isolamento multitenant do escritório contábil' },
      { name: 'cnpj', type: 'VARCHAR(14)', constraints: 'NOT NULL UNIQUE', description: 'CNPJ apenas dígitos com validação de formato' },
      { name: 'razao_social', type: 'VARCHAR(255)', constraints: 'NOT NULL', description: 'Razão social oficial na Receita Federal' },
      { name: 'nome_fantasia', type: 'VARCHAR(255)', description: 'Nome fantasia do estabelecimento' },
      { name: 'regime_tributario', type: 'VARCHAR(30)', constraints: "CHECK (regime_tributario IN ('SIMPLES_NACIONAL', 'LUCRO_PRESUMIDO', 'LUCRO_REAL', 'MEI'))", description: 'Regime para regras de impostos' },
      { name: 'inscricao_estadual', type: 'VARCHAR(20)', description: 'Inscrição estadual para operações de ICMS' },
      { name: 'inscricao_municipal', type: 'VARCHAR(20)', description: 'Inscrição municipal para ISSQN' },
      { name: 'certificado_a1_alias', type: 'VARCHAR(100)', description: 'Alias do certificado digital A1 no cofre/KMS' },
      { name: 'ativo', type: 'BOOLEAN', constraints: 'DEFAULT TRUE', description: 'Status ativo/inativo da empresa' },
      { name: 'created_at', type: 'TIMESTAMPTZ', constraints: 'DEFAULT clock_timestamp()', description: 'Data de auditoria de criação' }
    ],
    indexes: [
      { name: 'idx_empresas_tenant', columns: ['tenant_id', 'ativo'], type: 'BTREE', description: 'Filtragem rápida por escritório e empresas ativas' },
      { name: 'idx_empresas_cnpj', columns: ['cnpj'], type: 'UNIQUE', description: 'Busca direta por documento fiscal' }
    ]
  },
  {
    id: 'plano_contas',
    schema: 'contabil',
    name: 'plano_contas',
    description: 'Plano de contas contábil estruturado (Hierarquia, Máscara, Código Reduzido e Vinculação ao Plano Referencial da RFB/SPED).',
    columns: [
      { name: 'id', type: 'UUID', constraints: 'DEFAULT gen_random_uuid()', isPrimary: true, description: 'ID único da conta' },
      { name: 'empresa_id', type: 'UUID', constraints: 'NOT NULL', isForeign: true, references: 'core.empresas(id)', description: 'Empresa vinculada ou nulo para plano padrão' },
      { name: 'codigo_estrutural', type: 'VARCHAR(30)', constraints: 'NOT NULL', description: 'Ex: 1.1.01.01.0001 (níveis hierárquicos)' },
      { name: 'codigo_reduzido', type: 'INTEGER', constraints: 'NOT NULL', description: 'Código curto numérico para digitação rápida' },
      { name: 'descricao', type: 'VARCHAR(150)', constraints: 'NOT NULL', description: 'Nome da conta (ex: Caixa Geral, Banco Itaú)' },
      { name: 'natureza', type: 'CHAR(1)', constraints: "CHECK (natureza IN ('D', 'C'))", description: 'Natureza predominante (D = Devedora, C = Credora)' },
      { name: 'tipo_conta', type: 'VARCHAR(10)', constraints: "CHECK (tipo_conta IN ('SINTETICA', 'ANALITICA'))", description: 'Apenas analíticas recebem lançamentos' },
      { name: 'nivel', type: 'SMALLINT', constraints: 'NOT NULL', description: 'Grau hierárquico na árvore contábil (1 a 5)' },
      { name: 'codigo_referencial_rfb', type: 'VARCHAR(30)', description: 'Código correspondente no Plano Referencial da Receita Federal (ECD/ECF)' },
      { name: 'aceita_conciliacao', type: 'BOOLEAN', constraints: 'DEFAULT FALSE', description: 'Sinaliza contas de bancos/clientes/fornecedores' }
    ],
    indexes: [
      { name: 'idx_plano_empresa_estrutural', columns: ['empresa_id', 'codigo_estrutural'], type: 'UNIQUE', description: 'Garante unicidade do código na hierarquia da empresa' },
      { name: 'idx_plano_reduzido', columns: ['empresa_id', 'codigo_reduzido'], type: 'BTREE', description: 'Busca rápida durante lançamento contábil manual' }
    ]
  },
  {
    id: 'lancamentos_contabeis',
    schema: 'contabil',
    name: 'lancamentos_contabeis',
    description: 'Cabeçalho do lote e lançamento contábil em partidas dobradas. Particionada por ano/competência para alta performance.',
    partitionStrategy: 'RANGE (data_lancamento) - Partições anuais/mensais',
    columns: [
      { name: 'id', type: 'UUID', constraints: 'DEFAULT gen_random_uuid()', isPrimary: true, description: 'ID primário do lançamento' },
      { name: 'empresa_id', type: 'UUID', constraints: 'NOT NULL', isForeign: true, references: 'core.empresas(id)', description: 'Empresa do lançamento' },
      { name: 'data_lancamento', type: 'DATE', constraints: 'NOT NULL', description: 'Data do fato contábil (chave de particionamento)' },
      { name: 'competencia_ano_mes', type: 'INTEGER', constraints: 'NOT NULL', description: 'Ex: 202610 para agrupamento rápido de fechamento' },
      { name: 'numero_lote', type: 'VARCHAR(50)', description: 'Identificador do lote de integração (ex: FOLHA_102026, FISCAL_NFE)' },
      { name: 'historico_padrao_id', type: 'UUID', description: 'Referência ao histórico contábil padronizado' },
      { name: 'historico_complemento', type: 'TEXT', description: 'Texto explicativo do fato contábil' },
      { name: 'documento_origem', type: 'VARCHAR(100)', description: 'Número do cheque, fatura, chave NF-e ou contrato' },
      { name: 'total_debito', type: 'NUMERIC(15,2)', constraints: 'NOT NULL', description: 'Soma dos débitos (deve ser estritamente igual ao crédito)' },
      { name: 'total_credito', type: 'NUMERIC(15,2)', constraints: 'NOT NULL', description: 'Soma dos créditos (validação por trigger)' },
      { name: 'status', type: 'VARCHAR(20)', constraints: "DEFAULT 'EFETIVADO' CHECK (status IN ('RASCUNHO', 'EFETIVADO', 'ESTORNADO'))", description: 'Status do lançamento contábil' },
      { name: 'criado_por', type: 'UUID', description: 'Usuário ou rotina automática responsável' }
    ],
    indexes: [
      { name: 'idx_lancamentos_empresa_data', columns: ['empresa_id', 'data_lancamento'], type: 'BTREE', description: 'Leitura de extratos e balancetes por período' },
      { name: 'idx_lancamentos_competencia', columns: ['empresa_id', 'competencia_ano_mes'], type: 'BTREE', description: 'Agrupamentos mensais para DRE e Balanço' }
    ]
  },
  {
    id: 'partidas_contabeis',
    schema: 'contabil',
    name: 'partidas_contabeis',
    description: 'Itens das partidas dobradas (Débitos e Créditos com suporte a partidas simples e múltiplas).',
    partitionStrategy: 'RANGE vinculada à data do lançamento pai',
    columns: [
      { name: 'id', type: 'UUID', constraints: 'DEFAULT gen_random_uuid()', isPrimary: true, description: 'ID do item da partida' },
      { name: 'lancamento_id', type: 'UUID', constraints: 'NOT NULL', isForeign: true, references: 'contabil.lancamentos_contabeis(id) ON DELETE CASCADE', description: 'Lançamento cabeçalho' },
      { name: 'conta_id', type: 'UUID', constraints: 'NOT NULL', isForeign: true, references: 'contabil.plano_contas(id)', description: 'Conta contábil analítica movimentada' },
      { name: 'tipo', type: 'CHAR(1)', constraints: "NOT NULL CHECK (tipo IN ('D', 'C'))", description: 'D = Débito, C = Crédito' },
      { name: 'valor', type: 'NUMERIC(15,2)', constraints: 'NOT NULL CHECK (valor > 0)', description: 'Valor monetário estritamente positivo' },
      { name: 'centro_custo_id', type: 'UUID', description: 'Centro de custo opcional para rateio gerencial' }
    ],
    indexes: [
      { name: 'idx_partidas_lancamento', columns: ['lancamento_id'], type: 'BTREE', description: 'Junção com cabeçalho de lançamento' },
      { name: 'idx_partidas_conta_tipo', columns: ['conta_id', 'tipo'], type: 'BTREE', description: 'Cálculo de movimentação de conta contábil específica' }
    ]
  },
  {
    id: 'saldos_acumulados_mensais',
    schema: 'contabil',
    name: 'saldos_acumulados_mensais',
    description: 'Tabela de alta performance para emissão instantânea de Balancete e DRE O(1) sem escanear milhões de partidas.',
    columns: [
      { name: 'empresa_id', type: 'UUID', constraints: 'NOT NULL', isPrimary: true, description: 'Empresa' },
      { name: 'conta_id', type: 'UUID', constraints: 'NOT NULL', isPrimary: true, isForeign: true, references: 'contabil.plano_contas(id)', description: 'Conta contábil' },
      { name: 'ano_mes', type: 'INTEGER', constraints: 'NOT NULL', isPrimary: true, description: 'Competência (ex: 202610)' },
      { name: 'saldo_inicial', type: 'NUMERIC(15,2)', constraints: 'DEFAULT 0.00', description: 'Saldo no início do mês' },
      { name: 'total_debitos', type: 'NUMERIC(15,2)', constraints: 'DEFAULT 0.00', description: 'Soma de débitos do mês' },
      { name: 'total_creditos', type: 'NUMERIC(15,2)', constraints: 'DEFAULT 0.00', description: 'Soma de créditos do mês' },
      { name: 'saldo_final', type: 'NUMERIC(15,2)', constraints: 'NOT NULL', description: 'Saldo final consolidado' },
      { name: 'fechado', type: 'BOOLEAN', constraints: 'DEFAULT FALSE', description: 'Indica se a competência contábil está bloqueada contra alterações' }
    ],
    indexes: [
      { name: 'idx_saldos_competencia', columns: ['empresa_id', 'ano_mes'], type: 'BTREE', description: 'Extração instantânea do balancete mensal completo' }
    ]
  },
  {
    id: 'documentos_fiscais',
    schema: 'fiscal',
    name: 'documentos_fiscais',
    description: 'Repositório de notas fiscais (NF-e, NFS-e, NFC-e, CT-e) importadas via SEFAZ ou upload.',
    columns: [
      { name: 'id', type: 'UUID', constraints: 'DEFAULT gen_random_uuid()', isPrimary: true, description: 'ID único do documento fiscal' },
      { name: 'empresa_id', type: 'UUID', constraints: 'NOT NULL', isForeign: true, references: 'core.empresas(id)', description: 'Empresa emitente ou destinatária' },
      { name: 'chave_acesso', type: 'VARCHAR(44)', constraints: 'UNIQUE', description: 'Chave de 44 dígitos da NF-e / NFC-e / CT-e' },
      { name: 'modelo', type: 'VARCHAR(5)', constraints: 'NOT NULL', description: '55 (NF-e), 65 (NFC-e), 57 (CT-e), NFS-e' },
      { name: 'tipo_operacao', type: 'CHAR(1)', constraints: "CHECK (tipo_operacao IN ('E', 'S'))", description: 'E = Entrada, S = Saída' },
      { name: 'numero', type: 'INTEGER', constraints: 'NOT NULL', description: 'Número da nota' },
      { name: 'serie', type: 'VARCHAR(10)', constraints: 'NOT NULL', description: 'Série da nota' },
      { name: 'data_emissao', type: 'TIMESTAMPTZ', constraints: 'NOT NULL', description: 'Data e hora da emissão' },
      { name: 'cnpj_emitente', type: 'VARCHAR(14)', constraints: 'NOT NULL', description: 'CNPJ do emitente' },
      { name: 'cnpj_destinatario', type: 'VARCHAR(14)', description: 'CNPJ do destinatário' },
      { name: 'valor_total', type: 'NUMERIC(15,2)', constraints: 'NOT NULL', description: 'Valor total da nota fiscal' },
      { name: 'status_sefaz', type: 'VARCHAR(20)', constraints: "DEFAULT 'AUTORIZADA'", description: 'AUTORIZADA, CANCELADA, DENEGADA, INUTILIZADA' },
      { name: 'xml_armazenado_url', type: 'TEXT', description: 'Caminho no Cloud Storage ou MinIO para o arquivo XML' },
      { name: 'conciliado_contabil', type: 'BOOLEAN', constraints: 'DEFAULT FALSE', description: 'Se já gerou lançamento no módulo contábil' }
    ],
    indexes: [
      { name: 'idx_docs_empresa_emissao', columns: ['empresa_id', 'data_emissao'], type: 'BTREE', description: 'Apuração mensal de impostos' },
      { name: 'idx_docs_chave', columns: ['chave_acesso'], type: 'UNIQUE', description: 'Evita duplicidade de importação de XML' },
      { name: 'idx_docs_pendentes_contabil', columns: ['empresa_id'], type: 'PARTIAL', description: 'WHERE conciliado_contabil = FALSE' }
    ]
  },
  {
    id: 'obrigacoes_acessorias',
    schema: 'fiscal',
    name: 'obrigacoes_acessorias',
    description: 'Gestão de entregas de declarações fiscais e trabalhistas com controle de prazos e multas.',
    columns: [
      { name: 'id', type: 'UUID', constraints: 'DEFAULT gen_random_uuid()', isPrimary: true, description: 'ID da obrigação' },
      { name: 'empresa_id', type: 'UUID', constraints: 'NOT NULL', isForeign: true, references: 'core.empresas(id)', description: 'Empresa vinculada' },
      { name: 'sigla', type: 'VARCHAR(30)', constraints: 'NOT NULL', description: 'DCTFWeb, DEFIS, DAS, EFD-ICMS, EFD-Contribuições, eSocial, FGTS Digital' },
      { name: 'competencia', type: 'INTEGER', constraints: 'NOT NULL', description: 'Competência (ex: 202610)' },
      { name: 'data_vencimento', type: 'DATE', constraints: 'NOT NULL', description: 'Data limite legal de entrega' },
      { name: 'data_entrega', type: 'TIMESTAMPTZ', description: 'Data e hora do envio e protocolo' },
      { name: 'numero_recibo', type: 'VARCHAR(100)', description: 'Código do recibo de entrega da RFB ou SEFAZ' },
      { name: 'status', type: 'VARCHAR(20)', constraints: "DEFAULT 'PENDENTE' CHECK (status IN ('PENDENTE', 'EM_ANDAMENTO', 'ENTREGUE', 'ATRASADA', 'DISPENSADA'))", description: 'Status operacional da obrigação' },
      { name: 'responsavel_id', type: 'UUID', description: 'Colaborador do escritório responsável pela entrega' }
    ],
    indexes: [
      { name: 'idx_obrigacoes_vencimento_status', columns: ['data_vencimento', 'status'], type: 'BTREE', description: 'Dashboard de alertas de prazos e SLA do escritório' }
    ]
  }
];

export const SQL_DDL_PROPOSAL = `-- ====================================================================
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
`;

export const PERFORMANCE_PILLARS: PerformancePillar[] = [
  {
    title: 'Particionamento Declarativo de Tabelas Contábeis e Fiscais',
    category: 'database',
    impact: 'CRÍTICO',
    currentProblem: 'Tabelas monolíticas de lançamentos e itens de NF-e crescem para dezenas de milhões de linhas. Consultas de conciliação e relatórios fiscais degradam com table scan ou index scans gigantescos.',
    solution: 'Implementar particionamento nativo por faixa de data (RANGE PARTITIONING por ano/competência). O PostgreSQL elimina partições não consultadas na fase de planejamento da query (Partition Pruning).',
    estimatedGain: '70% a 90% menos I/O de disco em queries de competência específica.',
    language: 'sql',
    codeSnippet: `-- Exemplo: Criação de partição anual com partição default preventiva
CREATE TABLE contabil.lancamentos_contabeis (
    id UUID DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL,
    data_lancamento DATE NOT NULL,
    -- campos omitidos ...
    PRIMARY KEY (id, data_lancamento)
) PARTITION BY RANGE (data_lancamento);

-- Otimizador lê apenas o bloco do período desejado:
EXPLAIN ANALYZE 
SELECT * FROM contabil.lancamentos_contabeis
WHERE empresa_id = 'd5f7...' 
  AND data_lancamento BETWEEN '2026-10-01' AND '2026-10-31';`
  },
  {
    title: 'Balancete e DRE O(1) com Saldos Mensais Pré-Calculados',
    category: 'architecture',
    impact: 'CRÍTICO',
    currentProblem: 'Calcular o Balancete de Verificação somando `SELECT SUM(valor) FROM partidas` desde o início da empresa para cada conta é inviável em produção (latência de 8 a 40 segundos).',
    solution: 'Manter tabela agregada de saldos mensais (`saldos_acumulados_mensais`). Ao emitir o balancete de um mês, lê-se diretamente o registro da competência em O(1), atualizada em background ou via triggers no fechamento.',
    estimatedGain: 'Tempo de resposta de 35s cai para 45ms (redução de 99.8%).',
    language: 'sql',
    codeSnippet: `-- Consulta do balancete em O(1):
SELECT 
    p.codigo_estrutural,
    p.descricao,
    s.saldo_inicial,
    s.total_debitos,
    s.total_creditos,
    s.saldo_final
FROM contabil.plano_contas p
JOIN contabil.saldos_acumulados_mensais s 
  ON s.conta_id = p.id AND s.empresa_id = p.empresa_id
WHERE s.empresa_id = :empresaId
  AND s.ano_mes = 202610
ORDER BY p.codigo_estrutural ASC;`
  },
  {
    title: 'Processamento Assíncrono com Filas para XMLs e SPED',
    category: 'backend',
    impact: 'ALTO',
    currentProblem: 'Fazer o upload de 2.000 XMLs de notas fiscais ou gerar o arquivo SPED Fiscal na mesma thread HTTP do Node.js/NestJS bloqueia o Event Loop e estoura timeout de 30s ou memória da aplicação.',
    solution: 'Adotar fila distribuída (BullMQ + Redis). O controller HTTP recebe o lote, valida o token, salva no Storage e enfileira o job retornando HTTP 202 (Accepted) com progresso via WebSocket ou Server-Sent Events (SSE).',
    estimatedGain: 'Zero travamentos de tela; suporte a processamento de 50.000+ XMLs em paralelo.',
    language: 'typescript',
    codeSnippet: `// Controller desacoplado (Zero blocking):
@Post('importar-lote-xml')
async importarLoteXml(@UploadedFiles() files: Express.Multer.File[], @CurrentUser() user) {
  const job = await this.fiscalQueue.add('processar-lote-nfe', {
    empresaId: user.empresaId,
    arquivos: files.map(f => ({ nome: f.originalname, bufferBase64: f.buffer.toString('base64') }))
  }, { attempts: 3, backoff: 5000 });

  return { status: 'ENFILEIRADO', jobId: job.id, mensagem: 'Lote recebido para processamento assíncrono.' };
}`
  },
  {
    title: 'Keyset Pagination (Cursor) vs LIMIT/OFFSET em Extratos',
    category: 'database',
    impact: 'ALTO',
    currentProblem: 'O uso de `OFFSET 50000 LIMIT 50` faz o banco de dados ler e descartar 50.000 linhas em memória antes de entregar o resultado na tela de extrato contábil.',
    solution: 'Substituir por paginação por cursor (Keyset Pagination) baseada na tupla `(data_lancamento, id) < (:ultimoData, :ultimoId)`. O índice B-Tree localiza o ponto de partida instantaneamente.',
    estimatedGain: 'Tempo de consulta constante mesmo na página 1.000 do razão contábil.',
    language: 'sql',
    codeSnippet: `-- Paginação Keyset ultra-rápida (Tempo constante < 5ms):
SELECT id, data_lancamento, total_debito, historico_complemento
FROM contabil.lancamentos_contabeis
WHERE empresa_id = :empresaId
  AND (data_lancamento, id) < (:cursorData, :cursorId)
ORDER BY data_lancamento DESC, id DESC
LIMIT 50;`
  },
  {
    title: 'Connection Pooling Dedicado com PgBouncer',
    category: 'caching',
    impact: 'MÉDIO',
    currentProblem: 'Cada requisição abrindo nova conexão física com o PostgreSQL consome 10MB de RAM por processo backend e satura o limite `max_connections` em horários de pico fiscal (dia 20 do mês).',
    solution: 'Configurar PgBouncer em modo `transaction pooling` na frente do PostgreSQL com pool dimensionado para o número de CPU cores.',
    estimatedGain: 'Suporte a 1.000+ requisições simultâneas com apenas 25 conexões ativas no banco.',
    language: 'typescript',
    codeSnippet: `// Configuração otimizada no Drizzle / Prisma / TypeORM:
const db = new Pool({
  host: process.env.PG_BOUNCER_HOST, // Conecta no PgBouncer (porta 6432)
  port: 6432,
  database: 'ubj_contabil',
  max: 20, // Pool local controlado
  idleTimeoutMillis: 10000,
  connectionTimeoutMillis: 2000,
});`
  }
];

export const FEATURE_PROPOSALS: FeatureProposal[] = [
  {
    id: 'robo-dfe-sefaz',
    title: 'Robô de Captura Automática DFe SEFAZ (Certificado A1)',
    category: 'Fiscal',
    status: 'Essencial',
    complexity: 'Média',
    summary: 'Consulta automática e contínua do WebService de Distribuição DFe da Receita/SEFAZ para baixar todas as notas fiscais emitidas contra o CNPJ dos clientes do escritório sem depender de envio manual.',
    businessValue: 'Elimina 95% do retrabalho de cobrança de notas junto aos clientes no final do mês. Garante escrituração fiscal 100% tempestiva.',
    architectureDetails: [
      'Worker cron executando a cada 1 hora com rate limit respeitando o NSU da SEFAZ.',
      'Armazenamento seguro de certificados digitais A1 criptografados com AES-256 no banco ou cofre Vault.',
      'Importação automática do XML para a tabela `documentos_fiscais` e geração de pré-lançamento contábil.'
    ],
    techStack: ['Node.js Worker', 'libxmljs / fast-xml-parser', 'Redis para fila NSU', 'Criptografia AES-256']
  },
  {
    id: 'segregacao-monofasica',
    title: 'Auditor de PIS/COFINS Monofásico no Simples Nacional',
    category: 'Fiscal',
    status: 'Estratégica',
    complexity: 'Média',
    summary: 'Identificação automatizada de itens sujeitos à tributação monofásica de PIS/COFINS (autopeças, farmácias, cosméticos, bebidas frias) para segregação no PGDAS-D.',
    businessValue: 'Gera economia real de 3% a 6% do faturamento para os clientes do escritório contábil e permite serviços de recuperação tributária retroativa dos últimos 5 anos.',
    architectureDetails: [
      'Tabela referencial de NCMs monofásicos atualizada periodicamente.',
      'Varredura dos itens das NF-e e NFC-e na importação com classificação automática.',
      'Relatório analítico exportável para preenchimento direto no portal do Simples Nacional.'
    ],
    techStack: ['PostgreSQL JSONB', 'NCM Matcher Engine', 'Exportação Excel/PDF']
  },
  {
    id: 'conciliador-bancario-ai',
    title: 'Conciliador Inteligente OFX / Open Finance com Regras de Contrapartida',
    category: 'Financeiro',
    status: 'Recomendada',
    complexity: 'Alta',
    summary: 'Leitura de extratos bancários em formato OFX e integração Open Finance com motor de conciliação que sugere ou cria automaticamente a contrapartida contábil correta.',
    businessValue: 'Reduz o tempo de fechamento contábil de 2 dias por empresa para menos de 15 minutos.',
    architectureDetails: [
      'Parser de OFX com normalização de descrições bancárias (ex: "TED 033...", "PIX RECEBIDO...").',
      'Motor de regras baseadas em histórico: se CNPJ X recebeu PIX Y, sugere conta de cliente correspondente.',
      'Auditoria de conciliação com duplo clique para aprovação em lote.'
    ],
    techStack: ['ofx-parser', 'Similarity Matching', 'PostgreSQL Trigger de Atualização']
  },
  {
    id: 'portal-do-cliente-pix',
    title: 'Portal do Cliente com Guias de Impostos e PIX Copia-e-Cola',
    category: 'Automação',
    status: 'Essencial',
    complexity: 'Média',
    summary: 'Área exclusiva para os empresários clientes do UBJ Contábil acessarem seus balancetes, folha de pagamento, guias DAS/DARF com QR Code PIX dinâmico e enviarem recibos.',
    businessValue: 'Aumenta a percepção de valor do escritório, reduz inadimplência de guias e centraliza o atendimento eliminando perda de mensagens no WhatsApp.',
    architectureDetails: [
      'Autenticação segura JWT com isolamento de tenant por CNPJ do cliente.',
      'Geração de payload PIX Copia e Cola integrado às guias do Simples e DARFs.',
      'Notificações automáticas de vencimento via WhatsApp API / E-mail.'
    ],
    techStack: ['React SPA', 'Tailwind CSS', 'WhatsApp Business API', 'PIX EMV Engine']
  },
  {
    id: 'central-obrigacoes-sla',
    title: 'Painel Kanban de Obrigações Acessórias e Calendário Fiscal com SLA',
    category: 'Contábil',
    status: 'Essencial',
    complexity: 'Baixa',
    summary: 'Painel visual estilo Kanban e calendário para monitorar o status de todas as obrigações (DCTFWeb, EFD Reinf, DAS, DEFIS, ECD, ECF, FGTS Digital) de todas as empresas.',
    businessValue: 'Risco zero de multas por entrega fora do prazo legal (evita multas da Receita Federal que variam de R$ 500 a 2% do faturamento).',
    architectureDetails: [
      'Geração automatizada de tarefas no dia 1º de cada mês com base no regime tributário.',
      'Alarme visual de proximidade do vencimento (Verde, Amarelo, Vermelho).',
      'Upload do recibo com extração do número do protocolo.'
    ],
    techStack: ['React Kanban', 'PostgreSQL Vencimentos', 'Cron de Notificação']
  }
];

export const CODE_PRESETS: CodeAnalysisPreset[] = [
  {
    id: 'query-balancete-naive',
    title: 'Consulta Ingênua de Balancete (Gargalo Comum)',
    language: 'sql',
    code: `-- CÓDIGO ATUAL COMUM:
-- Soma todas as partidas da história do banco a cada clique no balancete:
SELECT 
    c.id,
    c.codigo_estrutural,
    c.descricao,
    COALESCE(SUM(CASE WHEN p.tipo = 'D' THEN p.valor ELSE 0 END), 0) AS total_debitos,
    COALESCE(SUM(CASE WHEN p.tipo = 'C' THEN p.valor ELSE 0 END), 0) AS total_creditos
FROM plano_contas c
LEFT JOIN partidas_contabeis p ON p.conta_id = c.id
LEFT JOIN lancamentos_contabeis l ON l.id = p.lancamento_id
WHERE l.empresa_id = 'a891-...'
  AND l.data_lancamento <= '2026-10-31'
GROUP BY c.id, c.codigo_estrutural, c.descricao
ORDER BY c.codigo_estrutural;`,
    diagnosis: 'Esta query executa um FULL SCAN nas tabelas de partidas e lançamentos a cada carregamento de página. Com 500.000 lançamentos, ela leva mais de 15 segundos e satura a CPU do banco de dados.',
    improvements: [
      'Utilizar tabela de saldos agregados mensais (saldos_acumulados_mensais).',
      'Filtrar apenas as movimentações do mês atual somando ao saldo_inicial do mês.',
      'Tempo de execução cai de 15.000ms para 3ms.'
    ],
    optimizedCode: `-- CÓDIGO OTIMIZADO UBJ CONTÁBIL:
-- Lê o saldo acumulado em O(1) diretamente da competência:
SELECT 
    p.codigo_estrutural,
    p.descricao,
    s.saldo_inicial,
    s.total_debitos,
    s.total_creditos,
    s.saldo_final
FROM contabil.plano_contas p
INNER JOIN contabil.saldos_acumulados_mensais s 
   ON s.conta_id = p.id AND s.empresa_id = p.empresa_id
WHERE s.empresa_id = 'a891-...'
  AND s.ano_mes = 202610
ORDER BY p.codigo_estrutural ASC;`
  },
  {
    id: 'partidas-dobradas-transaction',
    title: 'Gravação de Lançamento sem Transação ACID (Risco de Inconsistência)',
    language: 'typescript',
    code: `// CÓDIGO VULNERÁVEL:
async function salvarLancamento(dto: NovoLancamentoDto) {
  // Salva cabeçalho
  const lancamento = await db.lancamento.create({ data: dto.cabecalho });
  
  // Salva partidas em loop solto sem transação
  for (const item of dto.partidas) {
    await db.partida.create({
      data: {
        lancamentoId: lancamento.id,
        contaId: item.contaId,
        tipo: item.tipo,
        valor: item.valor
      }
    });
  }
  return lancamento;
}`,
    diagnosis: 'Se a conexão falhar ou houver exceção na metade do loop, o banco gravará débitos sem créditos, corrompendo a contabilidade da empresa e inviabilizando a ECD no SPED.',
    improvements: [
      'Executar em transação atômica estrita (db.$transaction ou BEGIN/COMMIT).',
      'Validar que Soma(Débito) === Soma(Crédito) antes de gravar.',
      'Inserir todas as partidas em lote único (batch insert) em vez de N queries.'
    ],
    optimizedCode: `// CÓDIGO ROBUSTO UBJ CONTÁBIL:
async function salvarLancamentoOtimizado(dto: NovoLancamentoDto) {
  const totalDebito = dto.partidas.filter(p => p.tipo === 'D').reduce((acc, p) => acc + p.valor, 0);
  const totalCredito = dto.partidas.filter(p => p.tipo === 'C').reduce((acc, p) => acc + p.valor, 0);

  if (Math.abs(totalDebito - totalCredito) > 0.001) {
    throw new BadRequestException('Erro Contábil: Total de Débitos diferente do Total de Créditos.');
  }

  return await db.$transaction(async (tx) => {
    const lancamento = await tx.lancamento.create({
      data: { ...dto.cabecalho, totalDebito, totalCredito }
    });

    await tx.partida.createMany({
      data: dto.partidas.map(p => ({
        lancamentoId: lancamento.id,
        contaId: p.contaId,
        tipo: p.tipo,
        valor: p.valor
      }))
    });

    return lancamento;
  });
}`
  }
];

export const INITIAL_CHECKLIST: AuditChecklistItem[] = [
  {
    id: 'db-1',
    category: 'Banco de Dados',
    title: 'Campos Monetários com NUMERIC(15,2)',
    description: 'Evitar FLOAT/DOUBLE para valores financeiros devido a erros de arredondamento IEEE 754.',
    impact: 'Crítica',
    completed: true
  },
  {
    id: 'db-2',
    category: 'Banco de Dados',
    title: 'Garantia de Partidas Dobradas via Constraint / Trigger',
    description: 'Garantir a nível de banco de dados que todo lançamento contábil possui débito estritamente igual ao crédito.',
    impact: 'Crítica',
    completed: true
  },
  {
    id: 'db-3',
    category: 'Banco de Dados',
    title: 'Plano de Contas com Código Estrutural e Código Reduzido',
    description: 'Permitir digitação rápida via código reduzido e amarração ao Plano Referencial da Receita Federal (ECD/ECF).',
    impact: 'Alta',
    completed: true
  },
  {
    id: 'db-4',
    category: 'Banco de Dados',
    title: 'Tabela de Saldos Acumulados Mensais',
    description: 'Evitar calcular somatórios históricos em tempo real a cada solicitação de DRE ou balancete.',
    impact: 'Crítica',
    completed: true
  },
  {
    id: 'perf-1',
    category: 'Performance',
    title: 'Particionamento de Tabelas Contábeis por Ano/Competência',
    description: 'Particionar lancamentos_contabeis e itens_notas por RANGE de data para isolar I/O.',
    impact: 'Crítica',
    completed: false
  },
  {
    id: 'perf-2',
    category: 'Performance',
    title: 'Keyset Pagination em Extratos e Relatórios Longos',
    description: 'Substituir OFFSET/LIMIT por paginação por cursor (data, id) para tempo de resposta sub-50ms.',
    impact: 'Alta',
    completed: false
  },
  {
    id: 'perf-3',
    category: 'Performance',
    title: 'Pool de Conexões PgBouncer em Transaction Mode',
    description: 'Evitar saturação de conexões físicas no PostgreSQL com múltiplas instâncias de backend.',
    impact: 'Alta',
    completed: false
  },
  {
    id: 'perf-4',
    category: 'Performance',
    title: 'Fila Redis / BullMQ para Importação de XMLs e SPED',
    description: 'Desacoplar processamento pesado de arquivos fiscais para workers em segundo plano.',
    impact: 'Crítica',
    completed: false
  },
  {
    id: 'feat-1',
    category: 'Funcionalidades',
    title: 'Captura Automática de DFe/NF-e via SEFAZ com Certificado A1',
    description: 'Baixar automaticamente todas as notas emitidas contra o CNPJ dos clientes.',
    impact: 'Crítica',
    completed: false
  },
  {
    id: 'feat-2',
    category: 'Funcionalidades',
    title: 'Módulo de Segregação Monofásica (PIS/COFINS)',
    description: 'Identificar automaticamente itens monofásicos e gerar créditos tributários para empresas do Simples.',
    impact: 'Alta',
    completed: false
  },
  {
    id: 'feat-3',
    category: 'Funcionalidades',
    title: 'Conciliação Bancária OFX com Machine Learning / Regras',
    description: 'Sugerir contrapartidas contábeis a partir de padrões bancários comuns.',
    impact: 'Alta',
    completed: false
  },
  {
    id: 'sec-1',
    category: 'Compliance & Segurança',
    title: 'Criptografia de Certificados A1 em Repouso (AES-256)',
    description: 'Armazenar chaves privadas e senhas de certificados em cofre criptografado com chave mestra rotacionada.',
    impact: 'Crítica',
    completed: true
  },
  {
    id: 'sec-2',
    category: 'Compliance & Segurança',
    title: 'Log de Auditoria Imutável para Lançamentos Estornados',
    description: 'Em contabilidade formal, lançamentos não são apagados (DELETE), e sim estornados com rastreabilidade completa.',
    impact: 'Crítica',
    completed: true
  }
];
