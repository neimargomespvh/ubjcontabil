import React, { useState } from 'react';
import { 
  FileCheck2, 
  TrendingUp, 
  Check, 
  AlertCircle, 
  Download, 
  Search, 
  Filter, 
  Percent,
  Sparkles,
  HelpCircle,
  ShieldCheck,
  Plus
} from 'lucide-react';
import { ItemMonofasico } from '../types';

const INITIAL_ITEMS: ItemMonofasico[] = [
  {
    id: 'mono-1',
    codigo: 'AUT-001',
    descricao: 'FILTRO DE OLEO MOTOR DIESEL PESADO',
    ncm: '8421.23.00',
    cstPis: '04', // Operação Tributável Monofásica - Revenda a Alíquota Zero
    cstCofins: '04',
    valorTotal: 18500.00,
    isMonofasico: true,
    categoria: 'Autopeças (Lei 10.485/2002)',
    economiaEstimadaPisCofins: 675.25
  },
  {
    id: 'mono-2',
    codigo: 'MED-042',
    descricao: 'DIPIRONA SODICA 500MG/ML GOTAS 20ML',
    ncm: '3004.90.99',
    cstPis: '04',
    cstCofins: '04',
    valorTotal: 34200.00,
    isMonofasico: true,
    categoria: 'Medicamentos (Lei 10.147/2000)',
    economiaEstimadaPisCofins: 1248.30
  },
  {
    id: 'mono-3',
    codigo: 'BEB-108',
    descricao: 'AGUA MINERAL NATURAL COM GAS 500ML',
    ncm: '2201.10.00',
    cstPis: '04',
    cstCofins: '04',
    valorTotal: 12400.00,
    isMonofasico: true,
    categoria: 'Bebidas Frias (Lei 13.097/2015)',
    economiaEstimadaPisCofins: 452.60
  },
  {
    id: 'mono-4',
    codigo: 'COS-019',
    descricao: 'SHAMPOO RECONSTRUTOR CAPILAR 300ML',
    ncm: '3305.10.00',
    cstPis: '04',
    cstCofins: '04',
    valorTotal: 9400.00,
    isMonofasico: true,
    categoria: 'Perfumaria e Cosméticos',
    economiaEstimadaPisCofins: 343.10
  },
  {
    id: 'mono-5',
    codigo: 'PAP-001',
    descricao: 'CADERNO BROCHURA 96 FLS CAPA DURA',
    ncm: '4820.20.00',
    cstPis: '01', // Tributação Normal
    cstCofins: '01',
    valorTotal: 15600.00,
    isMonofasico: false,
    categoria: 'Papelaria (Tributação Integral)',
    economiaEstimadaPisCofins: 0.00
  },
  {
    id: 'mono-6',
    codigo: 'FER-099',
    descricao: 'CONJUNTO DE FERRAMENTAS E CHAVES MANUAIS',
    ncm: '8206.00.00',
    cstPis: '01',
    cstCofins: '01',
    valorTotal: 22800.00,
    isMonofasico: false,
    categoria: 'Ferragens (Tributação Integral)',
    economiaEstimadaPisCofins: 0.00
  }
];

export const MonofasicoAuditModule: React.FC = () => {
  const [items, setItems] = useState<ItemMonofasico[]>(INITIAL_ITEMS);
  const [filterType, setFilterType] = useState<'todos' | 'monofasicos' | 'normais'>('todos');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [aliquotaEfetivaSimples, setAliquotaEfetivaSimples] = useState<number>(8.5); // % Total do Simples
  const [parcelaPisCofinsPercent, setParcelaPisCofinsPercent] = useState<number>(3.65); // % de PIS/COFINS da faixa

  const filteredItems = items.filter(item => {
    const matchesFilter = 
      filterType === 'todos' || 
      (filterType === 'monofasicos' && item.isMonofasico) ||
      (filterType === 'normais' && !item.isMonofasico);
    const matchesSearch = 
      item.descricao.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.ncm.includes(searchTerm) ||
      item.categoria.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesFilter && matchesSearch;
  });

  const faturamentoTotal = items.reduce((acc, i) => acc + i.valorTotal, 0);
  const faturamentoMonofasico = items.filter(i => i.isMonofasico).reduce((acc, i) => acc + i.valorTotal, 0);
  const percentualMonofasico = faturamentoTotal > 0 ? (faturamentoMonofasico / faturamentoTotal) * 100 : 0;

  // Cálculo da economia líquida no PGDAS-D:
  // Faturamento Monofásico * Alíquota PIS/COFINS segregada
  const economiaTotalMes = (faturamentoMonofasico * (parcelaPisCofinsPercent / 100));
  const economiaProjetadaAno = economiaTotalMes * 12;

  const handleExportCsv = () => {
    let csv = 'Codigo;Descricao;NCM;CST PIS;CST COFINS;Valor Total;Monofasico;Categoria;Economia PIS/COFINS\n';
    items.forEach(i => {
      csv += `${i.codigo};"${i.descricao}";${i.ncm};${i.cstPis};${i.cstCofins};${i.valorTotal.toFixed(2)};${i.isMonofasico ? 'SIM' : 'NAO'};"${i.categoria}";${i.economiaEstimadaPisCofins.toFixed(2)}\n`;
    });

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'segregacao_monofasica_pgdas_ubjcontabil.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 sm:p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-cyan-500/10 text-cyan-400 rounded-xl border border-cyan-500/20">
              <FileCheck2 className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-white tracking-tight">
                  Auditor de Segregação Monofásica (PIS/COFINS)
                </h2>
                <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 font-semibold">
                  Simples Nacional - PGDAS-D
                </span>
              </div>
              <p className="text-xs sm:text-sm text-slate-400 mt-0.5">
                Segregação automatizada de receitas monofásicas para evitar bitributação indevida de clientes do Simples.
              </p>
            </div>
          </div>

          <button
            onClick={handleExportCsv}
            className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-semibold text-xs transition-colors shadow-md shadow-cyan-950/40 cursor-pointer self-start md:self-auto"
          >
            <Download className="w-4 h-4" />
            Exportar Relatório PGDAS-D
          </button>
        </div>

        {/* Big Savings Metrics */}
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 mt-6 pt-5 border-t border-slate-800 text-xs">
          <div className="p-4 bg-emerald-950/30 rounded-xl border border-emerald-600/30">
            <div className="text-emerald-400 font-bold flex items-center gap-1.5 uppercase tracking-wider text-[10px]">
              <TrendingUp className="w-4 h-4" />
              Economia Líquida Mensal
            </div>
            <div className="text-2xl font-black text-white mt-1">
              R$ {economiaTotalMes.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
            </div>
            <div className="text-[11px] text-emerald-300/80 mt-1">
              Redução direta no valor da guia DAS
            </div>
          </div>

          <div className="p-4 bg-slate-800/40 rounded-xl border border-slate-700/50">
            <div className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
              Economia Projetada em 12 Meses
            </div>
            <div className="text-xl font-bold text-slate-100 mt-1">
              R$ {economiaProjetadaAno.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
            </div>
            <div className="text-[11px] text-slate-400 mt-1">
              Recuperável retroativo até 5 anos
            </div>
          </div>

          <div className="p-4 bg-slate-800/40 rounded-xl border border-slate-700/50">
            <div className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
              Receita com Tributação Monofásica
            </div>
            <div className="text-xl font-bold text-cyan-400 mt-1">
              R$ {faturamentoMonofasico.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
            </div>
            <div className="text-[11px] text-slate-400 mt-1">
              {percentualMonofasico.toFixed(1)}% do faturamento total
            </div>
          </div>

          <div className="p-4 bg-slate-800/40 rounded-xl border border-slate-700/50">
            <div className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
              Faturamento Global Apurado
            </div>
            <div className="text-xl font-bold text-slate-200 mt-1">
              R$ {faturamentoTotal.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
            </div>
            <div className="text-[11px] text-slate-400 mt-1">
              {items.length} itens auditados no período
            </div>
          </div>
        </div>
      </div>

      {/* Interactive Controls & Filters */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Buscar por descrição, NCM ou categoria..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="bg-slate-900 border border-slate-800 rounded-lg pl-8 pr-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 w-64"
            />
          </div>

          <div className="flex bg-slate-900 border border-slate-800 p-0.5 rounded-lg">
            <button
              onClick={() => setFilterType('todos')}
              className={`px-2.5 py-1 rounded-md transition-colors cursor-pointer ${
                filterType === 'todos' ? 'bg-cyan-600 text-white font-semibold' : 'text-slate-400 hover:text-white'
              }`}
            >
              Todos ({items.length})
            </button>
            <button
              onClick={() => setFilterType('monofasicos')}
              className={`px-2.5 py-1 rounded-md transition-colors cursor-pointer ${
                filterType === 'monofasicos' ? 'bg-cyan-600 text-white font-semibold' : 'text-slate-400 hover:text-white'
              }`}
            >
              Monofásicos ({items.filter(i => i.isMonofasico).length})
            </button>
            <button
              onClick={() => setFilterType('normais')}
              className={`px-2.5 py-1 rounded-md transition-colors cursor-pointer ${
                filterType === 'normais' ? 'bg-cyan-600 text-white font-semibold' : 'text-slate-400 hover:text-white'
              }`}
            >
              Tributação Normal ({items.filter(i => !i.isMonofasico).length})
            </button>
          </div>
        </div>

        <div className="flex items-center gap-3 text-slate-400 self-start sm:self-auto">
          <span className="font-medium">Parcela PIS/COFINS do DAS:</span>
          <div className="flex items-center gap-1 font-mono text-cyan-400 bg-slate-900 border border-slate-800 px-2 py-1 rounded-lg">
            <input
              type="number"
              step="0.05"
              min="0.5"
              max="9.0"
              value={parcelaPisCofinsPercent}
              onChange={(e) => setParcelaPisCofinsPercent(parseFloat(e.target.value) || 0)}
              className="w-12 bg-transparent text-right focus:outline-none text-white font-bold"
            />
            <span>%</span>
          </div>
        </div>
      </div>

      {/* Table of Items */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-800/70 text-slate-400 border-b border-slate-800 font-mono">
              <tr>
                <th className="py-2.5 px-3">Código</th>
                <th className="py-2.5 px-3">Descrição do Produto / Mercadoria</th>
                <th className="py-2.5 px-3">NCM</th>
                <th className="py-2.5 px-3 text-center">CST PIS/COFINS</th>
                <th className="py-2.5 px-3">Enquadramento Legal</th>
                <th className="py-2.5 px-3 text-right">Faturamento</th>
                <th className="py-2.5 px-3 text-right">Economia Gerada</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {filteredItems.map((item) => (
                <tr key={item.id} className="hover:bg-slate-800/30 transition-colors">
                  <td className="py-2.5 px-3 font-mono text-slate-400">{item.codigo}</td>
                  <td className="py-2.5 px-3 font-medium text-slate-200">
                    {item.descricao}
                  </td>
                  <td className="py-2.5 px-3 font-mono font-bold text-slate-300">
                    {item.ncm}
                  </td>
                  <td className="py-2.5 px-3 text-center font-mono">
                    <span className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                      item.isMonofasico ? 'bg-cyan-950/60 text-cyan-300 border border-cyan-800/40' : 'bg-slate-800 text-slate-400'
                    }`}>
                      CST {item.cstPis}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-slate-400 text-[11px]">
                    {item.isMonofasico ? (
                      <span className="text-emerald-400 font-semibold flex items-center gap-1">
                        <Check className="w-3 h-3" />
                        {item.categoria}
                      </span>
                    ) : (
                      <span className="text-slate-500">{item.categoria}</span>
                    )}
                  </td>
                  <td className="py-2.5 px-3 text-right font-mono text-slate-300">
                    R$ {item.valorTotal.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                  </td>
                  <td className="py-2.5 px-3 text-right font-mono font-bold whitespace-nowrap">
                    {item.isMonofasico ? (
                      <span className="text-emerald-400">
                        R$ {(item.valorTotal * (parcelaPisCofinsPercent / 100)).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                      </span>
                    ) : (
                      <span className="text-slate-600">-</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Legal Info Notice */}
      <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex items-start gap-3 text-xs text-slate-400">
        <ShieldCheck className="w-5 h-5 text-cyan-400 shrink-0 mt-0.5" />
        <p className="leading-relaxed">
          <strong>Fundamentação Legal (Receita Federal do Brasil):</strong> Conforme a Lei Complementar 123/2006, art. 18, § 4º-A, I, e Soluções de Consulta Cosit nº 225/2014 e 169/2019, o contribuinte optante pelo Simples Nacional que revende mercadorias com tributação monofásica de PIS/COFINS tem o direito legal de segregar as receitas correspondentes no PGDAS-D, desmarcando a incidência de PIS e COFINS no cálculo do DAS.
        </p>
      </div>
    </div>
  );
};
