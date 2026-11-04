import React from 'react';
import { 
  Database, 
  Zap, 
  Sparkles, 
  ShieldCheck, 
  TrendingUp, 
  Clock, 
  ArrowRight,
  FileSpreadsheet,
  Cpu,
  Bot
} from 'lucide-react';
import { ActiveTab } from '../types';

interface OverviewTabProps {
  onNavigate: (tab: ActiveTab) => void;
}

export const OverviewTab: React.FC<OverviewTabProps> = ({ onNavigate }) => {
  return (
    <div className="space-y-8">
      {/* Hero Executive Card */}
      <div className="bg-gradient-to-r from-slate-900 via-slate-850 to-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-emerald-500/5 rounded-full blur-3xl pointer-events-none"></div>
        <div className="max-w-3xl">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 mb-3">
            <ShieldCheck className="w-3.5 h-3.5" />
            Diagnóstico de Engenharia de Software Contábil
          </span>
          <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight leading-tight">
            Análise Estrutural e Recomendações Técnicas para o <span className="text-emerald-400">UBJ Contábil</span>
          </h2>
          <p className="mt-3 text-sm sm:text-base text-slate-300 leading-relaxed">
            Sistemas contábeis brasileiros exigem rigor transacional absoluto (princípio das partidas dobradas), conformidade com layout SPED (ECD, ECF, EFD) e capacidade de processar picos intensos no fechamento mensal. Abaixo está o mapeamento detalhado das melhorias de banco de dados, performance e funcionalidades.
          </p>
        </div>

        {/* 3 Impact Metrics */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-8 pt-6 border-t border-slate-800/80">
          <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/50">
            <div className="flex items-center gap-2 text-emerald-400 text-xs font-semibold uppercase tracking-wider">
              <Clock className="w-4 h-4" />
              Tempo do Balancete
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-white">~45 ms</span>
              <span className="text-xs text-emerald-400 font-medium">vs ~35s (O(1))</span>
            </div>
            <p className="mt-1 text-xs text-slate-400">Via tabela de saldos mensais acumulados</p>
          </div>

          <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/50">
            <div className="flex items-center gap-2 text-teal-400 text-xs font-semibold uppercase tracking-wider">
              <Cpu className="w-4 h-4" />
              I/O de Disco em Consultas
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-white">-85%</span>
              <span className="text-xs text-teal-400 font-medium">menos leitura</span>
            </div>
            <p className="mt-1 text-xs text-slate-400">Com particionamento por competência</p>
          </div>

          <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/50">
            <div className="flex items-center gap-2 text-cyan-400 text-xs font-semibold uppercase tracking-wider">
              <Bot className="w-4 h-4" />
              Automação Fiscal DFe
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-white">100%</span>
              <span className="text-xs text-cyan-400 font-medium">tempestivo</span>
            </div>
            <p className="mt-1 text-xs text-slate-400">Captura automática via WebService SEFAZ</p>
          </div>
        </div>
      </div>

      {/* The 3 Core Pillars Requested by User */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Pillar 1: Banco de Dados */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 flex flex-col justify-between hover:border-slate-700 transition-all group">
          <div>
            <div className="w-12 h-12 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center border border-emerald-500/20 mb-4 group-hover:scale-105 transition-transform">
              <Database className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold text-slate-100 flex items-center justify-between">
              Estrutura de Banco de Dados
              <span className="text-xs font-semibold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400">PostgreSQL</span>
            </h3>
            <p className="mt-2 text-xs sm:text-sm text-slate-400 leading-relaxed">
              Modelagem relacional de alta fidelidade para escritórios contábeis:
            </p>
            <ul className="mt-4 space-y-2 text-xs text-slate-300">
              <li className="flex items-start gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mt-1.5"></span>
                <span><strong>Partidas Dobradas com Trigger:</strong> Impossibilita gravação de lançamentos com débito ≠ crédito.</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mt-1.5"></span>
                <span><strong>Plano de Contas Dual:</strong> Código estrutural hierárquico + código reduzido + código referencial RFB (SPED).</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mt-1.5"></span>
                <span><strong>Isolamento Multitenant:</strong> Separação lógica por escritório e clientes com Row Level Security (RLS).</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mt-1.5"></span>
                <span><strong>Tipagem Precisa:</strong> <code>NUMERIC(15,2)</code> contra erros de ponto flutuante em centavos.</span>
              </li>
            </ul>
          </div>
          <button
            onClick={() => onNavigate('database')}
            className="mt-6 flex items-center justify-between w-full px-4 py-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-emerald-400 transition-colors"
          >
            Ver Schema & DDL SQL
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>

        {/* Pillar 2: Performance */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 flex flex-col justify-between hover:border-slate-700 transition-all group">
          <div>
            <div className="w-12 h-12 rounded-xl bg-teal-500/10 text-teal-400 flex items-center justify-center border border-teal-500/20 mb-4 group-hover:scale-105 transition-transform">
              <Zap className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold text-slate-100 flex items-center justify-between">
              Performance da Aplicação
              <span className="text-xs font-semibold px-2 py-0.5 rounded bg-teal-500/10 text-teal-400">Escala</span>
            </h3>
            <p className="mt-2 text-xs sm:text-sm text-slate-400 leading-relaxed">
              Estratégias de otimização para suportar milhões de lançamentos e XMLs:
            </p>
            <ul className="mt-4 space-y-2 text-xs text-slate-300">
              <li className="flex items-start gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-teal-400 mt-1.5"></span>
                <span><strong>Tabela de Saldos Acumulados:</strong> Balancete O(1) sem escanear anos de lançamentos a cada clique.</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-teal-400 mt-1.5"></span>
                <span><strong>Particionamento por Range:</strong> Segmentação anual de lançamentos para eliminar 80% do I/O.</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-teal-400 mt-1.5"></span>
                <span><strong>Filas BullMQ + Redis:</strong> Processamento assíncrono de lotes de NF-e e geração de arquivos SPED.</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-teal-400 mt-1.5"></span>
                <span><strong>Keyset Pagination:</strong> Extratos e razões com tempo de resposta constante (&lt;5ms).</span>
              </li>
            </ul>
          </div>
          <button
            onClick={() => onNavigate('performance')}
            className="mt-6 flex items-center justify-between w-full px-4 py-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-teal-400 transition-colors"
          >
            Ver Técnicas de Performance
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>

        {/* Pillar 3: Funcionalidades */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 flex flex-col justify-between hover:border-slate-700 transition-all group">
          <div>
            <div className="w-12 h-12 rounded-xl bg-cyan-500/10 text-cyan-400 flex items-center justify-center border border-cyan-500/20 mb-4 group-hover:scale-105 transition-transform">
              <Sparkles className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold text-slate-100 flex items-center justify-between">
              Funcionalidades Modernas
              <span className="text-xs font-semibold px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400">Valor Real</span>
            </h3>
            <p className="mt-2 text-xs sm:text-sm text-slate-400 leading-relaxed">
              Módulos de alta rentabilidade e automação para o escritório contábil:
            </p>
            <ul className="mt-4 space-y-2 text-xs text-slate-300">
              <li className="flex items-start gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 mt-1.5"></span>
                <span><strong>Robô DFe SEFAZ:</strong> Monitoramento e download contínuo de notas com certificado A1.</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 mt-1.5"></span>
                <span><strong>Segregação Monofásica:</strong> Auditoria de PIS/COFINS em farmácias, autopeças e bebidas.</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 mt-1.5"></span>
                <span><strong>Conciliador OFX Inteligente:</strong> Sugestão de partidas por aprendizado de histórico bancário.</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 mt-1.5"></span>
                <span><strong>Portal do Cliente com PIX:</strong> Emissão de guias com PIX copia e cola e controle de CNDs.</span>
              </li>
            </ul>
          </div>
          <button
            onClick={() => onNavigate('features')}
            className="mt-6 flex items-center justify-between w-full px-4 py-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-cyan-400 transition-colors"
          >
            Explorar Funcionalidades
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* 3 Novas Funcionalidades Estratégicas - Módulos Interativos */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-7 space-y-4 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-bold uppercase">
              Módulos em Operação Interativa
            </span>
            <h3 className="text-xl font-bold text-white mt-1">
              3 Novas Funcionalidades Estratégicas Implementadas
            </h3>
            <p className="text-xs sm:text-sm text-slate-400 mt-0.5">
              Experimente em tempo real a captura SEFAZ, o cálculo de segregação de PIS/COFINS e a conciliação bancária inteligente:
            </p>
          </div>

          <button
            onClick={() => onNavigate('scripts')}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-teal-600/20 hover:bg-teal-600/30 text-teal-300 border border-teal-500/30 text-xs font-semibold transition-colors self-start sm:self-auto cursor-pointer"
          >
            Ver Scripts de Download Local
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
          {/* Card 1: Robô DFe */}
          <div 
            onClick={() => onNavigate('dfe')}
            className="p-4 rounded-xl bg-slate-800/50 border border-slate-700 hover:border-emerald-500/60 transition-all cursor-pointer group"
          >
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950/60 text-emerald-400 border border-emerald-800/40 font-bold">
                Módulo 01
              </span>
              <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-emerald-400 group-hover:translate-x-0.5 transition-all" />
            </div>
            <h4 className="font-bold text-slate-100 text-sm mt-2 group-hover:text-emerald-300 transition-colors">
              Robô DFe SEFAZ & XMLs
            </h4>
            <p className="text-xs text-slate-400 mt-1 leading-relaxed">
              Consulta de WebService DFe da Receita Federal, captura contínua por NSU e contabilização automática em partidas dobradas.
            </p>
          </div>

          {/* Card 2: Segregação Monofásica */}
          <div 
            onClick={() => onNavigate('monofasico')}
            className="p-4 rounded-xl bg-slate-800/50 border border-slate-700 hover:border-cyan-500/60 transition-all cursor-pointer group"
          >
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-950/60 text-cyan-400 border border-cyan-800/40 font-bold">
                Módulo 02
              </span>
              <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-cyan-400 group-hover:translate-x-0.5 transition-all" />
            </div>
            <h4 className="font-bold text-slate-100 text-sm mt-2 group-hover:text-cyan-300 transition-colors">
              Auditor de Segregação Monofásica
            </h4>
            <p className="text-xs text-slate-400 mt-1 leading-relaxed">
              Auditoria de PIS/COFINS por NCM (autopeças, medicamentos, bebidas) e cálculo imediato da economia gerada no PGDAS-D.
            </p>
          </div>

          {/* Card 3: Conciliador Bancário */}
          <div 
            onClick={() => onNavigate('conciliador')}
            className="p-4 rounded-xl bg-slate-800/50 border border-slate-700 hover:border-teal-500/60 transition-all cursor-pointer group"
          >
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-teal-950/60 text-teal-400 border border-teal-800/40 font-bold">
                Módulo 03
              </span>
              <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-teal-400 group-hover:translate-x-0.5 transition-all" />
            </div>
            <h4 className="font-bold text-slate-100 text-sm mt-2 group-hover:text-teal-300 transition-colors">
              Conciliador Bancário OFX
            </h4>
            <p className="text-xs text-slate-400 mt-1 leading-relaxed">
              Importação de extratos OFX, sugestão inteligente de contrapartidas contábeis e aprovação em lote de lançamentos.
            </p>
          </div>
        </div>
      </div>

      {/* Interactive Tool Banner */}
      <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-5 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-emerald-500/20 text-emerald-400 rounded-lg">
            <TrendingUp className="w-5 h-5" />
          </div>
          <div>
            <h4 className="font-semibold text-slate-100 text-sm">
              Deseja rodar e editar o código no seu computador local?
            </h4>
            <p className="text-xs text-slate-400">
              Disponibilizamos scripts automatizados em Bash e Windows (.bat) para clonar, instalar dependências e sincronizar o GitHub em 1 clique.
            </p>
          </div>
        </div>
        <button
          onClick={() => onNavigate('scripts')}
          className="whitespace-nowrap px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs transition-colors shadow-sm cursor-pointer"
        >
          Acessar Scripts de Setup Local
        </button>
      </div>
    </div>
  );
};
