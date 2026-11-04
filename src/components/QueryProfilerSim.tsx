import React, { useState } from 'react';
import { 
  Activity, 
  Play, 
  CheckCircle2, 
  AlertTriangle, 
  Layers, 
  BarChart3, 
  RotateCcw,
  Sparkles,
  Server,
  Cpu
} from 'lucide-react';

interface Scenario {
  id: string;
  name: string;
  description: string;
  recordsVolume: number;
  naive: {
    latencyMs: number;
    ioMb: number;
    cpuPercent: number;
    method: string;
    explainPlan: string;
  };
  optimized: {
    latencyMs: number;
    ioMb: number;
    cpuPercent: number;
    method: string;
    explainPlan: string;
  };
}

const SCENARIOS: Scenario[] = [
  {
    id: 'balancete',
    name: 'Emissão de Balancete de Verificação (Mês Fechado)',
    description: 'Cálculo de débitos, créditos e saldos acumulados de todas as 450 contas ativas da empresa.',
    recordsVolume: 1000000,
    naive: {
      latencyMs: 14850,
      ioMb: 1250,
      cpuPercent: 98,
      method: 'Seq Scan em 1.000.000 de partidas + SUM() agregado em runtime',
      explainPlan: 'Seq Scan on partidas_contabeis (cost=0.00..45280.00 rows=1000000 width=16) -> Hash Aggregate -> Sort'
    },
    optimized: {
      latencyMs: 18,
      ioMb: 0.8,
      cpuPercent: 3,
      method: 'Index Scan em saldos_acumulados_mensais (O(1) por competência)',
      explainPlan: 'Index Scan using idx_saldos_competencia on saldos_acumulados_mensais (cost=0.42..15.20 rows=450 width=48)'
    }
  },
  {
    id: 'extrato-paginacao',
    name: 'Extrato do Livro Razão (Página 250 - Offset vs Cursor)',
    description: 'Navegação em páginas profundas do extrato de uma conta com 250.000 movimentações.',
    recordsVolume: 250000,
    naive: {
      latencyMs: 3200,
      ioMb: 340,
      cpuPercent: 78,
      method: 'LIMIT 50 OFFSET 25000 (O banco lê e descarta 25.000 linhas)',
      explainPlan: 'Limit (cost=3820.00..3825.00 rows=50) -> Seq Scan on lancamentos (descartando 25000 rows)'
    },
    optimized: {
      latencyMs: 4,
      ioMb: 0.1,
      cpuPercent: 1,
      method: 'Keyset Pagination por tupla (data_lancamento, id) < (:cursorData, :cursorId)',
      explainPlan: 'Index Scan using idx_lancamentos_empresa_data on lancamentos_contabeis (cost=0.42..8.44 rows=50)'
    }
  },
  {
    id: 'importacao-xml',
    name: 'Importação em Lote de 2.000 XMLs de NF-e',
    description: 'Upload de lote mensal de compras e vendas para escrituração e apuração fiscal.',
    recordsVolume: 2000,
    naive: {
      latencyMs: 42000,
      ioMb: 850,
      cpuPercent: 100,
      method: 'Parsing síncrono no Express + N inserts soltos em loop sem transação',
      explainPlan: 'Bloqueio total do Event Loop do Node.js -> Timeout HTTP 504 no cliente'
    },
    optimized: {
      latencyMs: 120, // Resposta HTTP imediata ao cliente com enqueue
      ioMb: 45,
      cpuPercent: 12,
      method: 'Enqueue BullMQ + Worker em background + COPY/Batch Insert no Postgres',
      explainPlan: 'HTTP 202 Accepted (<150ms) -> BullMQ Job -> Worker processa 2000 XMLs em 4.2s em thread separada'
    }
  }
];

export const QueryProfilerSim: React.FC = () => {
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>('balancete');
  const [multiplier, setMultiplier] = useState<number>(1);
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [simulationComplete, setSimulationComplete] = useState<boolean>(true);

  const scenario = SCENARIOS.find(s => s.id === selectedScenarioId) || SCENARIOS[0];

  const currentNaiveLatency = Math.round(scenario.naive.latencyMs * multiplier);
  const currentOptLatency = Math.max(2, Math.round(scenario.optimized.latencyMs * (multiplier > 2 ? 1.5 : 1)));
  const speedupFactor = Math.round(currentNaiveLatency / currentOptLatency);

  const runSimulation = () => {
    setIsSimulating(true);
    setSimulationComplete(false);
    setTimeout(() => {
      setIsSimulating(false);
      setSimulationComplete(true);
    }, 900);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 sm:p-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-emerald-500/10 text-emerald-400 rounded-xl border border-emerald-500/20">
              <Activity className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white tracking-tight">
                Simulador de Carga & Query Profiler Contábil
              </h2>
              <p className="text-xs sm:text-sm text-slate-400 mt-0.5">
                Compare em tempo real a latência, I/O e carga de CPU entre a abordagem legada e o modelo otimizado.
              </p>
            </div>
          </div>

          <button
            onClick={runSimulation}
            disabled={isSimulating}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold text-xs transition-colors self-start sm:self-auto cursor-pointer shadow-md shadow-emerald-950/40"
          >
            {isSimulating ? <RotateCcw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-white" />}
            {isSimulating ? 'Executando Benchmark...' : 'Executar Benchmark'}
          </button>
        </div>

        {/* Controls */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6 pt-5 border-t border-slate-800">
          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1.5">
              Cenário Contábil / Operação Crítica
            </label>
            <div className="grid grid-cols-1 gap-1.5">
              {SCENARIOS.map((s) => (
                <button
                  key={s.id}
                  onClick={() => { setSelectedScenarioId(s.id); setSimulationComplete(true); }}
                  className={`text-left px-3 py-2 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                    s.id === scenario.id
                      ? 'bg-emerald-950/40 border border-emerald-500/50 text-emerald-300'
                      : 'bg-slate-800/60 border border-slate-700/60 text-slate-400 hover:text-white'
                  }`}
                >
                  <div className="font-semibold">{s.name}</div>
                  <div className="text-[11px] text-slate-400 truncate">{s.description}</div>
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1.5">
              Volume de Dados do Escritório ({Math.round(scenario.recordsVolume * multiplier).toLocaleString('pt-BR')} registros)
            </label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { label: 'Normal (1x)', val: 1 },
                { label: 'Médio (2x)', val: 2 },
                { label: 'Alto (5x)', val: 5 }
              ].map(opt => (
                <button
                  key={opt.val}
                  onClick={() => setMultiplier(opt.val)}
                  className={`p-2.5 rounded-lg text-xs font-medium border text-center transition-all cursor-pointer ${
                    multiplier === opt.val
                      ? 'bg-emerald-600/20 border-emerald-500 text-emerald-300 font-bold'
                      : 'bg-slate-800/40 border-slate-700 text-slate-400 hover:text-white'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            {/* Speedup Box */}
            <div className="mt-4 p-4 rounded-xl bg-gradient-to-r from-emerald-950/40 to-slate-900 border border-emerald-600/30 flex items-center justify-between">
              <div>
                <span className="text-[10px] font-mono uppercase text-emerald-400 font-bold">Ganho de Performance</span>
                <div className="text-2xl font-black text-white">{speedupFactor}x mais rápido</div>
              </div>
              <div className="text-right">
                <span className="text-[10px] font-mono text-slate-400">Tempo de Resposta</span>
                <div className="text-xs font-bold text-emerald-400">
                  {currentNaiveLatency} ms &rarr; {currentOptLatency} ms
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Comparison Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Naive Approach Card */}
        <div className="bg-slate-900 border border-rose-900/40 rounded-xl p-5 sm:p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-rose-500"></span>
              <h3 className="font-bold text-slate-200 text-base">Abordagem Comum / Ingênua</h3>
            </div>
            <span className="text-xs font-mono font-bold text-rose-400 bg-rose-950/50 px-2 py-0.5 rounded border border-rose-800/40">
              {currentNaiveLatency} ms
            </span>
          </div>

          <p className="text-xs text-rose-200/80 leading-relaxed">
            {scenario.naive.method}
          </p>

          {/* Metric Bars */}
          <div className="space-y-3 pt-2">
            <div>
              <div className="flex justify-between text-xs text-slate-400 mb-1">
                <span>Latência Total</span>
                <span className="text-rose-400 font-mono font-bold">{(currentNaiveLatency / 1000).toFixed(2)}s</span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                <div className="bg-rose-500 h-2 rounded-full transition-all duration-700" style={{ width: '95%' }}></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs text-slate-400 mb-1">
                <span>Leitura de Disco (I/O)</span>
                <span className="text-rose-400 font-mono font-bold">{Math.round(scenario.naive.ioMb * multiplier)} MB</span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                <div className="bg-rose-500 h-2 rounded-full transition-all duration-700" style={{ width: '85%' }}></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs text-slate-400 mb-1">
                <span>Uso de CPU do PostgreSQL</span>
                <span className="text-rose-400 font-mono font-bold">{scenario.naive.cpuPercent}%</span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                <div className="bg-rose-500 h-2 rounded-full transition-all duration-700" style={{ width: `${scenario.naive.cpuPercent}%` }}></div>
              </div>
            </div>
          </div>

          <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 text-[11px] font-mono text-rose-300/80 overflow-x-auto">
            <span className="text-slate-500 block text-[10px]">EXPLAIN PLAN:</span>
            {scenario.naive.explainPlan}
          </div>
        </div>

        {/* Optimized Approach Card */}
        <div className="bg-slate-900 border border-emerald-500/40 rounded-xl p-5 sm:p-6 space-y-4 shadow-lg shadow-emerald-950/20">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400"></span>
              <h3 className="font-bold text-slate-100 text-base">Arquitetura UBJ Contábil Otimizada</h3>
            </div>
            <span className="text-xs font-mono font-bold text-emerald-400 bg-emerald-950/50 px-2 py-0.5 rounded border border-emerald-500/40">
              {currentOptLatency} ms
            </span>
          </div>

          <p className="text-xs text-emerald-200/90 leading-relaxed">
            {scenario.optimized.method}
          </p>

          {/* Metric Bars */}
          <div className="space-y-3 pt-2">
            <div>
              <div className="flex justify-between text-xs text-slate-400 mb-1">
                <span>Latência Total</span>
                <span className="text-emerald-400 font-mono font-bold">{currentOptLatency} ms</span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                <div className="bg-emerald-400 h-2 rounded-full transition-all duration-700" style={{ width: '4%' }}></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs text-slate-400 mb-1">
                <span>Leitura de Disco (I/O)</span>
                <span className="text-emerald-400 font-mono font-bold">{scenario.optimized.ioMb} MB</span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                <div className="bg-emerald-400 h-2 rounded-full transition-all duration-700" style={{ width: '3%' }}></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs text-slate-400 mb-1">
                <span>Uso de CPU do PostgreSQL</span>
                <span className="text-emerald-400 font-mono font-bold">{scenario.optimized.cpuPercent}%</span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                <div className="bg-emerald-400 h-2 rounded-full transition-all duration-700" style={{ width: `${scenario.optimized.cpuPercent}%` }}></div>
              </div>
            </div>
          </div>

          <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 text-[11px] font-mono text-emerald-300/90 overflow-x-auto">
            <span className="text-slate-500 block text-[10px]">EXPLAIN PLAN:</span>
            {scenario.optimized.explainPlan}
          </div>
        </div>
      </div>
    </div>
  );
};
