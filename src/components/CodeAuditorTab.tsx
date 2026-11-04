import React, { useState } from 'react';
import { 
  Code2, 
  Play, 
  Check, 
  Copy, 
  AlertTriangle, 
  CheckCircle2, 
  Sparkles, 
  FileCode, 
  Info,
  RefreshCw
} from 'lucide-react';
import { CODE_PRESETS } from '../data/blueprintData';

interface AuditResult {
  score: number; // 0 to 100
  rating: 'Crítico' | 'Atenção' | 'Bom' | 'Excelente';
  issues: {
    severity: 'alta' | 'media' | 'baixa';
    title: string;
    description: string;
    fixSuggestion: string;
  }[];
  positives: string[];
  refactoredCode: string;
}

export const CodeAuditorTab: React.FC = () => {
  const [selectedPresetId, setSelectedPresetId] = useState<string>('query-balancete-naive');
  const [userCode, setUserCode] = useState<string>(CODE_PRESETS[0].code);
  const [auditResult, setAuditResult] = useState<AuditResult | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);

  // Load a preset
  const handleSelectPreset = (presetId: string) => {
    setSelectedPresetId(presetId);
    const preset = CODE_PRESETS.find(p => p.id === presetId);
    if (preset) {
      setUserCode(preset.code);
      setAuditResult(null);
    }
  };

  // Run the code audit engine
  const handleAnalyze = () => {
    setIsAnalyzing(true);

    setTimeout(() => {
      const code = userCode;
      const issues: AuditResult['issues'] = [];
      const positives: string[] = [];
      let score = 95;

      // Rule: Check for FLOAT or DOUBLE in financial schemas
      if (/float|double\s+precision|real/i.test(code)) {
        issues.push({
          severity: 'alta',
          title: 'Uso de tipo Float/Double em valores monetários',
          description: 'Números de ponto flutuante causam erros de arredondamento em centavos (IEEE 754), gerando divergências tributárias e fiscais na ECD/ECF.',
          fixSuggestion: 'Substitua por NUMERIC(15,2) ou DECIMAL(15,2) com precisão fixa.'
        });
        score -= 25;
      }

      // Rule: Check for missing transaction in double entry
      if (
        (/lancamento|partida/i.test(code) && /create|insert/i.test(code)) &&
        !/\$transaction|transaction|BEGIN|COMMIT/i.test(code)
      ) {
        issues.push({
          severity: 'alta',
          title: 'Gravação de Partidas Contábeis sem Transação Atômica (ACID)',
          description: 'Lançamentos contábeis exigem débito e crédito gravados juntos. Se ocorrer erro no meio da gravação, o banco ficará desbalanceado.',
          fixSuggestion: 'Encapsule a gravação do cabeçalho e partidas em uma transação única (BEGIN ... COMMIT ou tx.$transaction).'
        });
        score -= 30;
      }

      // Rule: Check for naive SUM query on entire ledger
      if (/SUM\s*\(/i.test(code) && /FROM\s+(partidas|lancamentos)/i.test(code) && !/saldos_acumulados/i.test(code)) {
        issues.push({
          severity: 'alta',
          title: 'Cálculo de Balancete em Tempo Real (Full Scan)',
          description: 'Somar todas as partidas da história a cada carregamento de página degrada drasticamente conforme o volume cresce acima de 50k linhas.',
          fixSuggestion: 'Implemente uma tabela de saldos agregados mensais (saldos_acumulados_mensais) e consulte em O(1).'
        });
        score -= 20;
      }

      // Rule: OFFSET pagination
      if (/OFFSET\s+\d+/i.test(code)) {
        issues.push({
          severity: 'media',
          title: 'Paginação Ineficiente via OFFSET',
          description: 'O PostgreSQL precisa escanear e descartar todas as linhas anteriores ao OFFSET antes de retornar os resultados.',
          fixSuggestion: 'Utilize Keyset Pagination (Cursor) filtrando por (data_lancamento, id) < (:cursorData, :cursorId).'
        });
        score -= 15;
      }

      // Rule: Missing equality validation (debito == credito)
      if (/lancamento/i.test(code) && !/debito.*credito|sum\(.*debito\)|valida.*partidas/i.test(code)) {
        issues.push({
          severity: 'alta',
          title: 'Ausência de Validação do Princípio das Partidas Dobradas',
          description: 'Não foi detectada verificação estrita de igualdade entre o somatório de Débitos e Créditos antes da persistência.',
          fixSuggestion: 'Adicione uma constraint de trigger no banco de dados e validação no DTO garantindo total_debito === total_credito.'
        });
        score -= 20;
      }

      // Rule: SELECT *
      if (/SELECT\s+\*\s+FROM/i.test(code)) {
        issues.push({
          severity: 'baixa',
          title: 'Uso de SELECT * em tabelas contábeis',
          description: 'Retorna colunas desnecessárias e impede o uso de Index-Only Scans.',
          fixSuggestion: 'Selecione explicitamente apenas os campos necessários (ex: id, data, codigo_estrutural, valor).'
        });
        score -= 10;
      }

      // Positive aspects
      if (/NUMERIC\s*\(\s*15\s*,\s*2\s*\)/i.test(code)) {
        positives.push('Uso correto de NUMERIC(15,2) para precisão de centavos.');
      }
      if (/PARTITION\s+BY/i.test(code)) {
        positives.push('Uso de particionamento declarativo no PostgreSQL.');
      }
      if (/transaction|tx\./i.test(code)) {
        positives.push('Uso de transações atômicas para integridade contábil.');
      }
      if (/saldos_acumulados/i.test(code)) {
        positives.push('Otimização com tabela de saldos mensais agregados.');
      }

      if (positives.length === 0) {
        positives.push('Código sintaticamente estruturado para análise.');
      }

      const finalScore = Math.max(20, Math.min(100, score));
      let rating: AuditResult['rating'] = 'Excelente';
      if (finalScore < 50) rating = 'Crítico';
      else if (finalScore < 75) rating = 'Atenção';
      else if (finalScore < 90) rating = 'Bom';

      // Pick corresponding optimized snippet
      const matchingPreset = CODE_PRESETS.find(p => p.id === selectedPresetId);
      const refactoredCode = matchingPreset 
        ? matchingPreset.optimizedCode 
        : `-- VERSÃO REFATORADA SUGERIDA PARA UBJ CONTÁBIL:
-- 1. Garante transação atômica
-- 2. Lê saldos em O(1)
SELECT 
    p.codigo_estrutural,
    p.descricao,
    s.saldo_final
FROM contabil.plano_contas p
JOIN contabil.saldos_acumulados_mensais s 
  ON s.conta_id = p.id AND s.empresa_id = p.empresa_id
WHERE s.empresa_id = :empresaId
  AND s.ano_mes = 202610
ORDER BY p.codigo_estrutural ASC;`;

      setAuditResult({
        score: finalScore,
        rating,
        issues,
        positives,
        refactoredCode
      });

      setIsAnalyzing(false);
    }, 600);
  };

  const handleCopyRefactored = () => {
    if (auditResult?.refactoredCode) {
      navigator.clipboard.writeText(auditResult.refactoredCode);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 sm:p-6">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-emerald-500/10 text-emerald-400 rounded-xl border border-emerald-500/20">
            <Code2 className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white tracking-tight">
              Analisador de Código, Queries SQL & Schemas
            </h2>
            <p className="text-xs sm:text-sm text-slate-400 mt-0.5">
              Como o repositório GitHub está protegido, cole abaixo trechos do seu projeto (SQL, Prisma, Drizzle, TypeORM, Controllers) para auditar vulnerabilidades e gargalos em tempo real.
            </p>
          </div>
        </div>

        {/* Quick Presets */}
        <div className="mt-5 pt-4 border-t border-slate-800 flex items-center gap-2 flex-wrap text-xs">
          <span className="text-slate-400 font-semibold mr-1 flex items-center gap-1">
            <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
            Exemplos Prontos para Testar:
          </span>
          {CODE_PRESETS.map((p) => (
            <button
              key={p.id}
              onClick={() => handleSelectPreset(p.id)}
              className={`px-3 py-1.5 rounded-lg border font-medium transition-colors cursor-pointer ${
                selectedPresetId === p.id
                  ? 'bg-emerald-600/20 text-emerald-300 border-emerald-500/50 font-semibold'
                  : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-white'
              }`}
            >
              {p.title}
            </button>
          ))}
        </div>
      </div>

      {/* Editor & Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Code Input Box */}
        <div className="lg:col-span-6 space-y-3">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="font-semibold text-slate-300 flex items-center gap-1.5">
              <FileCode className="w-4 h-4 text-emerald-400" />
              Cole aqui o código do UBJ Contábil (SQL, Prisma, TS):
            </span>
            <span className="font-mono text-[11px] text-slate-500">
              {userCode.length} caracteres
            </span>
          </div>

          <div className="relative rounded-xl overflow-hidden border border-slate-800 bg-slate-950 focus-within:border-emerald-500 transition-colors">
            <textarea
              value={userCode}
              onChange={(e) => setUserCode(e.target.value)}
              rows={16}
              className="w-full p-4 font-mono text-xs text-slate-200 bg-transparent resize-y focus:outline-none leading-relaxed"
              placeholder="Cole aqui seu script SQL, schema de banco de dados ou controllers..."
            />
          </div>

          <button
            onClick={handleAnalyze}
            disabled={isAnalyzing || !userCode.trim()}
            className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-bold text-xs transition-all shadow-md shadow-emerald-950/40 cursor-pointer"
          >
            {isAnalyzing ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                Auditando Código com Regras Contábeis...
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-white" />
                Auditar Código & Obter Sugestões Otimizadas
              </>
            )}
          </button>
        </div>

        {/* Audit Results Box */}
        <div className="lg:col-span-6 space-y-4">
          {auditResult ? (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-5">
              {/* Score Header */}
              <div className="flex items-center justify-between p-4 rounded-xl bg-slate-800/60 border border-slate-700/60">
                <div>
                  <span className="text-[10px] font-mono uppercase text-slate-400">Classificação de Saúde</span>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-xl font-black text-white">{auditResult.rating}</span>
                    <span className={`text-xs font-bold px-2 py-0.5 rounded ${
                      auditResult.score >= 80 
                        ? 'bg-emerald-500/20 text-emerald-400' 
                        : auditResult.score >= 60 
                        ? 'bg-amber-500/20 text-amber-400' 
                        : 'bg-rose-500/20 text-rose-400'
                    }`}>
                      Score: {auditResult.score}/100
                    </span>
                  </div>
                </div>

                <div className="w-12 h-12 rounded-full border-4 border-slate-700 flex items-center justify-center font-bold text-sm text-slate-200">
                  {auditResult.score}
                </div>
              </div>

              {/* Issues Identified */}
              {auditResult.issues.length > 0 && (
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-rose-400 mb-2 flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    Problemas & Gargalos Detectados ({auditResult.issues.length})
                  </h4>
                  <div className="space-y-2.5 max-h-56 overflow-y-auto pr-1">
                    {auditResult.issues.map((issue, i) => (
                      <div key={i} className="p-3 rounded-lg bg-rose-950/20 border border-rose-900/40 text-xs">
                        <div className="font-bold text-rose-300 flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-full bg-rose-500"></span>
                          {issue.title}
                        </div>
                        <p className="text-rose-200/80 mt-1 leading-relaxed">
                          {issue.description}
                        </p>
                        <div className="mt-2 text-[11px] text-emerald-300 bg-emerald-950/30 p-2 rounded border border-emerald-900/30">
                          <strong>Como corrigir:</strong> {issue.fixSuggestion}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Positives */}
              {auditResult.positives.length > 0 && (
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-emerald-400 mb-1.5 flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Pontos Positivos Identificados
                  </h4>
                  <ul className="text-xs text-slate-300 space-y-1">
                    {auditResult.positives.map((pos, i) => (
                      <li key={i} className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                        {pos}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Optimized Code Snippet */}
              <div>
                <div className="flex items-center justify-between text-xs text-slate-400 mb-1.5">
                  <span className="font-semibold text-emerald-400 flex items-center gap-1">
                    <Sparkles className="w-3.5 h-3.5" />
                    Versão Refatorada Sugerida:
                  </span>
                  <button
                    onClick={handleCopyRefactored}
                    className="flex items-center gap-1 text-[11px] text-slate-300 hover:text-white transition-colors cursor-pointer"
                  >
                    {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                    {copied ? 'Copiado!' : 'Copiar Código'}
                  </button>
                </div>
                <pre className="p-3 bg-slate-950 border border-slate-800 rounded-lg text-xs font-mono text-emerald-300/90 overflow-x-auto leading-relaxed max-h-56">
                  <code>{auditResult.refactoredCode}</code>
                </pre>
              </div>
            </div>
          ) : (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center flex flex-col items-center justify-center min-h-[360px]">
              <div className="w-12 h-12 rounded-xl bg-slate-800 text-slate-400 flex items-center justify-center mb-3">
                <Code2 className="w-6 h-6" />
              </div>
              <h3 className="font-bold text-slate-200 text-base">Pronto para Analisar</h3>
              <p className="text-xs text-slate-400 max-w-sm mt-1 leading-relaxed">
                Clique em <strong>Auditar Código</strong> ao lado para executar a verificação contábil automática de transações, tipos monetários e performance.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
