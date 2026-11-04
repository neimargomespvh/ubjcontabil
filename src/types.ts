export type ActiveTab = 
  | 'overview' 
  | 'database' 
  | 'performance' 
  | 'features' 
  | 'dfe' 
  | 'monofasico' 
  | 'conciliador' 
  | 'scripts' 
  | 'profiler' 
  | 'auditor' 
  | 'checklist';

export interface DfeNotaFiscal {
  id: string;
  nsu: number;
  chaveAcesso: string;
  numero: number;
  serie: string;
  dataEmissao: string;
  cnpjEmitente: string;
  razaoEmitente: string;
  cnpjDestinatario: string;
  razaoDestinatario: string;
  valorTotal: number;
  valorIcms: number;
  valorPis: number;
  valorCofins: number;
  statusSefaz: 'AUTORIZADA' | 'CANCELADA' | 'DENEGADA';
  conciliadoContabil: boolean;
  itensCount: number;
}

export interface ItemMonofasico {
  id: string;
  codigo: string;
  descricao: string;
  ncm: string;
  cstPis: string;
  cstCofins: string;
  valorTotal: number;
  isMonofasico: boolean;
  categoria: string;
  economiaEstimadaPisCofins: number; // ~3.65% a 9.25%
}

export interface ExtratoTransacao {
  id: string;
  data: string;
  descricao: string;
  documento: string;
  valor: number;
  tipo: 'D' | 'C'; // D = Saída do banco, C = Entrada no banco
  categoria: string;
  contaSugeridaCodigo: string;
  contaSugeridaDescricao: string;
  status: 'PENDENTE' | 'CONCILIADO';
  grauConfianca: number; // 0 to 100%
  historicoSugerido: string;
}


export interface DatabaseTable {
  id: string;
  name: string;
  schema: string;
  description: string;
  columns: {
    name: string;
    type: string;
    constraints?: string;
    description: string;
    isPrimary?: boolean;
    isForeign?: boolean;
    references?: string;
  }[];
  indexes: {
    name: string;
    columns: string[];
    type: 'BTREE' | 'GIN' | 'BRIN' | 'UNIQUE' | 'PARTIAL';
    description: string;
  }[];
  partitionStrategy?: string;
}

export interface PerformancePillar {
  title: string;
  category: 'database' | 'backend' | 'architecture' | 'caching';
  impact: 'CRÍTICO' | 'ALTO' | 'MÉDIO';
  currentProblem: string;
  solution: string;
  codeSnippet: string;
  language: string;
  estimatedGain: string;
}

export interface FeatureProposal {
  id: string;
  title: string;
  category: 'Fiscal' | 'Contábil' | 'Financeiro' | 'Automação' | 'Segurança';
  status: 'Recomendada' | 'Estratégica' | 'Essencial';
  complexity: 'Baixa' | 'Média' | 'Alta';
  summary: string;
  businessValue: string;
  architectureDetails: string[];
  techStack: string[];
}

export interface AuditChecklistItem {
  id: string;
  category: 'Banco de Dados' | 'Performance' | 'Funcionalidades' | 'Compliance & Segurança';
  title: string;
  description: string;
  impact: 'Alta' | 'Média' | 'Crítica';
  completed: boolean;
}

export interface CodeAnalysisPreset {
  id: string;
  title: string;
  language: 'sql' | 'typescript' | 'prisma';
  code: string;
  diagnosis: string;
  improvements: string[];
  optimizedCode: string;
}
