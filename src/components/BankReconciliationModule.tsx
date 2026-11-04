import React, { useState } from 'react';
import { 
  CreditCard, 
  ArrowUpRight, 
  ArrowDownLeft, 
  CheckCircle2, 
  Clock, 
  Check, 
  Upload, 
  FileSpreadsheet, 
  Sparkles, 
  ShieldCheck,
  Building,
  AlertCircle
} from 'lucide-react';
import { ExtratoTransacao } from '../types';

const INITIAL_TRANSACTIONS: ExtratoTransacao[] = [
  {
    id: 'tx-1',
    data: '2026-10-25',
    descricao: 'PIX RECEBIDO - DROGARIA SAO PAULO S/A',
    documento: 'PIX-908123',
    valor: 14250.00,
    tipo: 'C', // Entrada
    categoria: 'Recebimento de Clientes',
    contaSugeridaCodigo: '1.1.02.01.0001',
    contaSugeridaDescricao: 'Clientes Nacionais a Receber',
    status: 'CONCILIADO',
    grauConfianca: 99,
    historicoSugerido: 'Vlr. ref. recebimento duplicata NF-e 12903 via PIX'
  },
  {
    id: 'tx-2',
    data: '2026-10-26',
    descricao: 'PAGTO ELETRON COBRANCA - DISTRIB AUTO PECAS',
    documento: 'BOL-449102',
    valor: 8450.00,
    tipo: 'D', // Saída
    categoria: 'Pagamento de Fornecedores',
    contaSugeridaCodigo: '2.1.01.01.0001',
    contaSugeridaDescricao: 'Fornecedores Nacionais a Pagar',
    status: 'CONCILIADO',
    grauConfianca: 98,
    historicoSugerido: 'Vlr. ref. liquidação boleto fornecedor NF-e 45812'
  },
  {
    id: 'tx-3',
    data: '2026-10-28',
    descricao: 'TAR CTA PACOTE MENSAL SERV BANCARIOS',
    documento: 'TAR-00912',
    valor: 89.90,
    tipo: 'D', // Saída
    categoria: 'Despesas Financeiras',
    contaSugeridaCodigo: '3.3.02.01.0002',
    contaSugeridaDescricao: 'Despesas com Tarifas Bancárias',
    status: 'PENDENTE',
    grauConfianca: 100,
    historicoSugerido: 'Vlr. ref. tarifa pacote de serviços bancários do mês'
  },
  {
    id: 'tx-4',
    data: '2026-10-29',
    descricao: 'PIX ENVIADO - ENEL DISTRIBUICAO ENERGIA',
    documento: 'PIX-776211',
    valor: 1240.50,
    tipo: 'D', // Saída
    categoria: 'Despesas de Energia Elétrica',
    contaSugeridaCodigo: '3.3.01.02.0005',
    contaSugeridaDescricao: 'Energia Elétrica e Água',
    status: 'PENDENTE',
    grauConfianca: 96,
    historicoSugerido: 'Vlr. ref. pagamento fatura de energia elétrica'
  },
  {
    id: 'tx-5',
    data: '2026-10-30',
    descricao: 'TED RECEBIDA - MERCADO LIVRE REPASSE VENDAS',
    documento: 'TED-889012',
    valor: 7600.00,
    tipo: 'C', // Entrada
    categoria: 'Receita de Vendas E-commerce',
    contaSugeridaCodigo: '1.1.02.01.0005',
    contaSugeridaDescricao: 'Adquirentes e Marketplaces a Receber',
    status: 'PENDENTE',
    grauConfianca: 94,
    historicoSugerido: 'Vlr. ref. repasse de vendas e-commerce marketplace'
  },
  {
    id: 'tx-6',
    data: '2026-10-31',
    descricao: 'RESGATE APLICACAO FINANCEIRA CDB FACIL',
    documento: 'APL-11209',
    valor: 20000.00,
    tipo: 'C', // Entrada
    categoria: 'Resgate de Aplicações',
    contaSugeridaCodigo: '1.1.01.03.0001',
    contaSugeridaDescricao: 'Aplicações Financeiras de Liquidez Imediata',
    status: 'PENDENTE',
    grauConfianca: 92,
    historicoSugerido: 'Vlr. ref. resgate de aplicação CDB Fácil'
  }
];

export const BankReconciliationModule: React.FC = () => {
  const [transactions, setTransactions] = useState<ExtratoTransacao[]>(INITIAL_TRANSACTIONS);
  const [selectedBank, setSelectedBank] = useState<string>('itau');
  const [feedback, setFeedback] = useState<string | null>(null);

  const saldoExtratoBancario = 42800.00;
  const pendentes = transactions.filter(t => t.status === 'PENDENTE');
  const conciliados = transactions.filter(t => t.status === 'CONCILIADO');

  // Conciliar item individual
  const handleConciliarItem = (id: string) => {
    setTransactions(prev => prev.map(t => 
      t.id === id ? { ...t, status: 'CONCILIADO' } : t
    ));
    setFeedback('Lançamento contábil integrado e conciliado com sucesso!');
    setTimeout(() => setFeedback(null), 3000);
  };

  // Conciliar todas as pendências automáticas
  const handleConciliarLote = () => {
    setTransactions(prev => prev.map(t => ({ ...t, status: 'CONCILIADO' })));
    setFeedback(`Conciliação em lote executada: ${pendentes.length} lançamentos gerados no diário contábil!`);
    setTimeout(() => setFeedback(null), 4000);
  };

  const totalEntradas = transactions.filter(t => t.tipo === 'C').reduce((acc, t) => acc + t.valor, 0);
  const totalSaidas = transactions.filter(t => t.tipo === 'D').reduce((acc, t) => acc + t.valor, 0);

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 sm:p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-teal-500/10 text-teal-400 rounded-xl border border-teal-500/20">
              <CreditCard className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-white tracking-tight">
                  Conciliador Bancário Inteligente (OFX / Open Finance)
                </h2>
                <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-teal-500/10 text-teal-400 border border-teal-500/20 font-semibold">
                  Machine Rules Engine
                </span>
              </div>
              <p className="text-xs sm:text-sm text-slate-400 mt-0.5">
                Correspondência contábil automática entre extratos bancários e partidas dobradas.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 self-start md:self-auto">
            {pendentes.length > 0 && (
              <button
                onClick={handleConciliarLote}
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs transition-colors shadow-md shadow-emerald-950/40 cursor-pointer"
              >
                <Check className="w-4 h-4" />
                Conciliar Pendentes ({pendentes.length})
              </button>
            )}
          </div>
        </div>

        {/* Bank & Balance Overview */}
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 mt-6 pt-5 border-t border-slate-800 text-xs">
          <div className="p-3 bg-slate-800/40 rounded-lg border border-slate-700/50">
            <span className="text-slate-400 block text-[10px] uppercase font-semibold">Conta Bancária</span>
            <div className="font-bold text-slate-200 mt-1 flex items-center gap-1.5">
              <Building className="w-3.5 h-3.5 text-teal-400" />
              Itaú Unibanco (Ag. 0422 / C/C 89210-4)
            </div>
            <div className="text-[11px] text-teal-400 mt-0.5">Conta Contábil: 1.1.01.02.0001</div>
          </div>

          <div className="p-3 bg-slate-800/40 rounded-lg border border-slate-700/50">
            <span className="text-slate-400 block text-[10px] uppercase font-semibold">Saldo no Extrato Bancário</span>
            <div className="font-bold text-white mt-1 text-base font-mono">
              R$ {saldoExtratoBancario.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
            </div>
            <div className="text-[11px] text-emerald-400 mt-0.5">Posição conciliada com o banco</div>
          </div>

          <div className="p-3 bg-slate-800/40 rounded-lg border border-slate-700/50">
            <span className="text-slate-400 block text-[10px] uppercase font-semibold">Entradas / Recebimentos</span>
            <div className="font-bold text-emerald-400 mt-1 text-base font-mono">
              + R$ {totalEntradas.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
            </div>
            <div className="text-[11px] text-slate-400 mt-0.5">PIX, TEDs e Liquidações</div>
          </div>

          <div className="p-3 bg-slate-800/40 rounded-lg border border-slate-700/50">
            <span className="text-slate-400 block text-[10px] uppercase font-semibold">Saídas / Pagamentos</span>
            <div className="font-bold text-rose-400 mt-1 text-base font-mono">
              - R$ {totalSaidas.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
            </div>
            <div className="text-[11px] text-slate-400 mt-0.5">Boletos, PIX e Despesas</div>
          </div>
        </div>

        {/* Feedback Alert */}
        {feedback && (
          <div className="mt-4 p-3 rounded-lg bg-emerald-950/40 border border-emerald-500/40 text-emerald-300 text-xs flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
            <span>{feedback}</span>
          </div>
        )}
      </div>

      {/* Side-by-Side Reconciliation Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
        <div className="p-4 border-b border-slate-800 flex items-center justify-between text-xs">
          <span className="font-bold text-slate-200 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-teal-400" />
            Transações do Extrato vs. Contrapartidas Contábeis Sugeridas
          </span>
          <span className="text-slate-400 font-mono">
            {conciliados.length} conciliados &bull; {pendentes.length} pendentes
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-800/70 text-slate-400 border-b border-slate-800 font-mono">
              <tr>
                <th className="py-2.5 px-3">Data</th>
                <th className="py-2.5 px-3">Extrato Bancário (Histórico Original)</th>
                <th className="py-2.5 px-3 text-right">Valor</th>
                <th className="py-2.5 px-3">Contrapartida Contábil Sugerida</th>
                <th className="py-2.5 px-3 text-center">Confiança</th>
                <th className="py-2.5 px-3 text-center">Status</th>
                <th className="py-2.5 px-3 text-center">Ação</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {transactions.map((tx) => (
                <tr key={tx.id} className="hover:bg-slate-800/30 transition-colors">
                  <td className="py-3 px-3 font-mono text-slate-400 text-[11px] whitespace-nowrap">
                    {tx.data}
                  </td>
                  <td className="py-3 px-3">
                    <div className="font-semibold text-slate-200 flex items-center gap-1.5">
                      {tx.tipo === 'C' ? (
                        <span title="Entrada"><ArrowDownLeft className="w-3.5 h-3.5 text-emerald-400" /></span>
                      ) : (
                        <span title="Saída"><ArrowUpRight className="w-3.5 h-3.5 text-rose-400" /></span>
                      )}
                      {tx.descricao}
                    </div>
                    <div className="font-mono text-slate-500 text-[10px]">Doc: {tx.documento}</div>
                  </td>
                  <td className={`py-3 px-3 text-right font-mono font-bold whitespace-nowrap ${
                    tx.tipo === 'C' ? 'text-emerald-400' : 'text-slate-200'
                  }`}>
                    {tx.tipo === 'C' ? '+' : '-'} R$ {tx.valor.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                  </td>
                  <td className="py-3 px-3">
                    <div className="font-mono text-cyan-400 text-xs font-semibold">
                      {tx.contaSugeridaCodigo}
                    </div>
                    <div className="text-slate-300 text-[11px]">
                      {tx.contaSugeridaDescricao}
                    </div>
                    <div className="text-slate-500 text-[10px] italic">
                      {tx.historicoSugerido}
                    </div>
                  </td>
                  <td className="py-3 px-3 text-center">
                    <span className="font-mono text-[11px] font-bold text-emerald-400 bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-900/40">
                      {tx.grauConfianca}%
                    </span>
                  </td>
                  <td className="py-3 px-3 text-center">
                    {tx.status === 'CONCILIADO' ? (
                      <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        <Check className="w-3 h-3" />
                        Conciliado
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
                        <Clock className="w-3 h-3" />
                        Pendente
                      </span>
                    )}
                  </td>
                  <td className="py-3 px-3 text-center whitespace-nowrap">
                    {tx.status === 'PENDENTE' ? (
                      <button
                        onClick={() => handleConciliarItem(tx.id)}
                        className="px-2.5 py-1 rounded-md bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 border border-emerald-500/30 text-[11px] font-semibold transition-colors cursor-pointer"
                      >
                        Aprovar
                      </button>
                    ) : (
                      <span className="text-slate-600 text-[11px] font-mono">Efetivado</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
