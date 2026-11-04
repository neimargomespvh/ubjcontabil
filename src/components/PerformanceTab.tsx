import React, { useState } from 'react';
import { 
  Zap, 
  AlertTriangle, 
  CheckCircle2, 
  TrendingUp, 
  Copy, 
  Check, 
  Cpu, 
  Server, 
  Workflow,
  Clock
} from 'lucide-react';
import { PERFORMANCE_PILLARS } from '../data/blueprintData';
import { PerformancePillar } from '../types';

export const PerformanceTab: React.FC = () => {
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const handleCopyCode = (code: string, index: number) => {
    navigator.clipboard.writeText(code);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  return (
    <div className="space-y-8">
      {/* Overview Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 sm:p-6">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-teal-500/10 text-teal-400 rounded-xl border border-teal-500/20">
            <Zap className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white tracking-tight">
              Plano Diretor de Performance & Escalabilidade
            </h2>
            <p className="text-xs sm:text-sm text-slate-400 mt-1">
              Arquitetura projetada para suportar até 10+ milhões de lançamentos e processar 50.000 XMLs/mês sem lentidão.
            </p>
          </div>
        </div>

        {/* High-Level Architecture Topology */}
        <div className="mt-6 pt-5 border-t border-slate-800 grid grid-cols-1 sm:grid-cols-4 gap-3 text-center">
          <div className="p-3 rounded-lg bg-slate-800/40 border border-slate-700/50">
            <span className="text-[10px] font-mono uppercase text-slate-400">1. Frontend / UI</span>
            <div className="font-bold text-sm text-slate-200 mt-0.5">Keyset Pagination</div>
            <p className="text-[11px] text-slate-400 mt-1">Zero OFFSET; cursor baseado em data/id</p>
          </div>

          <div className="p-3 rounded-lg bg-slate-800/40 border border-slate-700/50">
            <span className="text-[10px] font-mono uppercase text-slate-400">2. Backend / API</span>
            <div className="font-bold text-sm text-slate-200 mt-0.5">BullMQ + Redis</div>
            <p className="text-[11px] text-slate-400 mt-1">Assíncrono para XMLs, SPED e DFe</p>
          </div>

          <div className="p-3 rounded-lg bg-slate-800/40 border border-slate-700/50">
            <span className="text-[10px] font-mono uppercase text-slate-400">3. Connection Pool</span>
            <div className="font-bold text-sm text-slate-200 mt-0.5">PgBouncer (Port 6432)</div>
            <p className="text-[11px] text-slate-400 mt-1">Modo transação; economia de RAM</p>
          </div>

          <div className="p-3 rounded-lg bg-slate-800/40 border border-slate-700/50">
            <span className="text-[10px] font-mono uppercase text-slate-400">4. Engine de Dados</span>
            <div className="font-bold text-sm text-slate-200 mt-0.5">Particionamento + O(1)</div>
            <p className="text-[11px] text-slate-400 mt-1">Balancetes lidos de tabela agregada</p>
          </div>
        </div>
      </div>

      {/* Pillars Breakdown */}
      <div className="space-y-6">
        {PERFORMANCE_PILLARS.map((pillar, idx) => (
          <div key={idx} className="bg-slate-900 border border-slate-800 rounded-xl p-5 sm:p-6 shadow-sm hover:border-slate-700 transition-all">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-4">
              <div className="flex items-center gap-3">
                <span className="w-7 h-7 rounded-lg bg-teal-500/10 text-teal-400 flex items-center justify-center font-mono font-bold text-xs border border-teal-500/20">
                  0{idx + 1}
                </span>
                <h3 className="text-base sm:text-lg font-bold text-white">
                  {pillar.title}
                </h3>
              </div>
              <div className="flex items-center gap-2 self-start sm:self-auto">
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded font-mono ${
                  pillar.impact === 'CRÍTICO' 
                    ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                    : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                }`}>
                  IMPACTO {pillar.impact}
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                  {pillar.category.toUpperCase()}
                </span>
              </div>
            </div>

            {/* Problem vs Solution Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 my-4">
              <div className="p-3.5 bg-rose-950/20 border border-rose-900/30 rounded-lg">
                <div className="flex items-center gap-1.5 text-xs font-bold text-rose-300 mb-1">
                  <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
                  Gargalo / Sintoma Típico
                </div>
                <p className="text-xs text-rose-200/90 leading-relaxed">
                  {pillar.currentProblem}
                </p>
              </div>

              <div className="p-3.5 bg-emerald-950/20 border border-emerald-900/30 rounded-lg">
                <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-300 mb-1">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  Solução Arquitetural
                </div>
                <p className="text-xs text-emerald-200/90 leading-relaxed">
                  {pillar.solution}
                </p>
              </div>
            </div>

            {/* Code Snippet Box */}
            <div className="rounded-lg overflow-hidden border border-slate-800 bg-slate-950 mt-4">
              <div className="bg-slate-900/80 px-4 py-2 border-b border-slate-800 flex items-center justify-between text-xs font-mono text-slate-400">
                <span className="text-teal-400 font-semibold">{pillar.language.toUpperCase()} IMPLEMENTAÇÃO</span>
                <button
                  onClick={() => handleCopyCode(pillar.codeSnippet, idx)}
                  className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-white transition-colors cursor-pointer"
                >
                  {copiedIndex === idx ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  {copiedIndex === idx ? 'Copiado!' : 'Copiar'}
                </button>
              </div>
              <pre className="p-4 text-xs font-mono text-slate-300 overflow-x-auto leading-relaxed">
                <code>{pillar.codeSnippet}</code>
              </pre>
            </div>

            {/* Gain Badge */}
            <div className="mt-4 flex items-center gap-2 text-xs font-medium text-emerald-400 bg-emerald-500/5 px-3 py-2 rounded-lg border border-emerald-500/20">
              <TrendingUp className="w-4 h-4 shrink-0" />
              <span><strong>Ganho Projetado:</strong> {pillar.estimatedGain}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
