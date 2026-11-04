import React, { useState } from 'react';
import { 
  Bot, 
  RotateCw, 
  FileText, 
  CheckCircle2, 
  Clock, 
  ShieldCheck, 
  ArrowRight, 
  Search, 
  Layers, 
  Check, 
  Download,
  AlertCircle,
  Eye,
  FileSpreadsheet
} from 'lucide-react';
import { DfeNotaFiscal } from '../types';

const INITIAL_DFE_NOTES: DfeNotaFiscal[] = [
  {
    id: 'dfe-1',
    nsu: 84921,
    chaveAcesso: '35261012345678000190550010000458121098234812',
    numero: 45812,
    serie: '1',
    dataEmissao: '2026-10-28 14:22:10',
    cnpjEmitente: '12.345.678/0001-90',
    razaoEmitente: 'DISTRIBUIDORA DE AUTO PECAS BRASIL LTDA',
    cnpjDestinatario: '98.765.432/0001-10',
    razaoDestinatario: 'UBJ CONTABIL - CLIENTE COMERCIO S/A',
    valorTotal: 8450.00,
    valorIcms: 1521.00,
    valorPis: 139.42,
    valorCofins: 642.20,
    statusSefaz: 'AUTORIZADA',
    conciliadoContabil: false,
    itensCount: 14
  },
  {
    id: 'dfe-2',
    nsu: 84922,
    chaveAcesso: '35261098765432000111550020000129031045982134',
    numero: 12903,
    serie: '2',
    dataEmissao: '2026-10-29 09:15:40',
    cnpjEmitente: '44.333.222/0001-55',
    razaoEmitente: 'FARMACEUTICA CENTRAL S/A',
    cnpjDestinatario: '98.765.432/0001-10',
    razaoDestinatario: 'UBJ CONTABIL - CLIENTE COMERCIO S/A',
    valorTotal: 14200.50,
    valorIcms: 2556.09,
    valorPis: 234.30,
    valorCofins: 1079.24,
    statusSefaz: 'AUTORIZADA',
    conciliadoContabil: true,
    itensCount: 32
  },
  {
    id: 'dfe-3',
    nsu: 84923,
    chaveAcesso: '35261077889900000133550010000084721012984711',
    numero: 8472,
    serie: '1',
    dataEmissao: '2026-10-30 11:45:00',
    cnpjEmitente: '77.889.900/0001-33',
    razaoEmitente: 'INDUSTRIA DE BEBIDAS E ALIMENTOS NORTE LTDA',
    cnpjDestinatario: '98.765.432/0001-10',
    razaoDestinatario: 'UBJ CONTABIL - CLIENTE COMERCIO S/A',
    valorTotal: 5320.00,
    valorIcms: 957.60,
    valorPis: 87.78,
    valorCofins: 404.32,
    statusSefaz: 'AUTORIZADA',
    conciliadoContabil: false,
    itensCount: 8
  },
  {
    id: 'dfe-4',
    nsu: 84924,
    chaveAcesso: '35261055443322000188550010000031121087451209',
    numero: 3112,
    serie: '1',
    dataEmissao: '2026-10-31 16:02:18',
    cnpjEmitente: '55.443.322/0001-88',
    razaoEmitente: 'SOLUCOES EM TECNOLOGIA E HARDWARE ME',
    cnpjDestinatario: '98.765.432/0001-10',
    razaoDestinatario: 'UBJ CONTABIL - CLIENTE COMERCIO S/A',
    valorTotal: 2890.00,
    valorIcms: 520.20,
    valorPis: 47.68,
    valorCofins: 219.64,
    statusSefaz: 'AUTORIZADA',
    conciliadoContabil: false,
    itensCount: 3
  }
];

export const DfeSefazModule: React.FC = () => {
  const [notes, setNotes] = useState<DfeNotaFiscal[]>(INITIAL_DFE_NOTES);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [selectedNote, setSelectedNote] = useState<DfeNotaFiscal | null>(null);
  const [lastSyncTime, setLastSyncTime] = useState<string>('Hoje, às 17:15');
  const [feedbackMsg, setFeedbackMsg] = useState<string | null>(null);
  const [currentNsu, setCurrentNsu] = useState<number>(84924);

  // Simular consulta ao WebService DFe SEFAZ
  const handleSyncSefaz = () => {
    setIsSyncing(true);
    setFeedbackMsg(null);

    setTimeout(() => {
      const nextNsu = currentNsu + 1;
      const newNote: DfeNotaFiscal = {
        id: `dfe-${nextNsu}`,
        nsu: nextNsu,
        chaveAcesso: `352610${Math.floor(10000000000000 + Math.random() * 90000000000000)}550010000${Math.floor(10000 + Math.random() * 90000)}10`,
        numero: Math.floor(10000 + Math.random() * 50000),
        serie: '1',
        dataEmissao: new Date().toISOString().replace('T', ' ').substring(0, 19),
        cnpjEmitente: '21.884.992/0001-44',
        razaoEmitente: 'ATACADISTA BRASILEIRO DE INSUMOS LTDA',
        cnpjDestinatario: '98.765.432/0001-10',
        razaoDestinatario: 'UBJ CONTABIL - CLIENTE COMERCIO S/A',
        valorTotal: 6780.00,
        valorIcms: 1220.40,
        valorPis: 111.87,
        valorCofins: 515.28,
        statusSefaz: 'AUTORIZADA',
        conciliadoContabil: false,
        itensCount: 19
      };

      setNotes(prev => [newNote, ...prev]);
      setCurrentNsu(nextNsu);
      setIsSyncing(false);
      setLastSyncTime('Agora mesmo');
      setFeedbackMsg(`Sincronização SEFAZ concluída: 1 nova NF-e identificada (NSU #${nextNsu}).`);
      setTimeout(() => setFeedbackMsg(null), 4000);
    }, 1200);
  };

  // Contabilizar nota individual ou em lote
  const handleContabilizar = (id?: string) => {
    if (id) {
      setNotes(prev => prev.map(n => n.id === id ? { ...n, conciliadoContabil: true } : n));
      setFeedbackMsg('Lançamento contábil em partidas dobradas gerado com sucesso no módulo Contábil!');
    } else {
      setNotes(prev => prev.map(n => ({ ...n, conciliadoContabil: true })));
      setFeedbackMsg('Todas as notas fiscais pendentes foram contabilizadas em lote!');
    }
    setTimeout(() => setFeedbackMsg(null), 3500);
  };

  const totalValor = notes.reduce((acc, n) => acc + n.valorTotal, 0);
  const pendentesCount = notes.filter(n => !n.conciliadoContabil).length;

  return (
    <div className="space-y-6">
      {/* Header & Status Card */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 sm:p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-emerald-500/10 text-emerald-400 rounded-xl border border-emerald-500/20">
              <Bot className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-white tracking-tight">
                  Robô de Captura Automática DFe SEFAZ
                </h2>
                <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold">
                  WebService Distribuição DFe
                </span>
              </div>
              <p className="text-xs sm:text-sm text-slate-400 mt-0.5">
                Monitoramento contínuo da Receita Federal e SEFAZ via Certificado Digital A1.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 self-start md:self-auto">
            <button
              onClick={handleSyncSefaz}
              disabled={isSyncing}
              className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold text-xs transition-colors shadow-md shadow-emerald-950/40 cursor-pointer"
            >
              <RotateCw className={`w-4 h-4 ${isSyncing ? 'animate-spin' : ''}`} />
              {isSyncing ? 'Consultando SEFAZ...' : 'Consultar DFe Agora'}
            </button>

            {pendentesCount > 0 && (
              <button
                onClick={() => handleContabilizar()}
                className="flex items-center gap-1.5 px-3.5 py-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-emerald-400 border border-slate-700 text-xs font-semibold transition-colors cursor-pointer"
              >
                <Check className="w-4 h-4" />
                Contabilizar Lote ({pendentesCount})
              </button>
            )}
          </div>
        </div>

        {/* Certificate and Monitor Info Bar */}
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 mt-6 pt-5 border-t border-slate-800 text-xs">
          <div className="p-3 bg-slate-800/40 rounded-lg border border-slate-700/50">
            <div className="text-slate-400 flex items-center gap-1.5 font-medium">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
              Certificado Digital A1
            </div>
            <div className="font-bold text-slate-200 mt-1">UBJ CONTABIL MATRIZ</div>
            <div className="text-[11px] text-emerald-400 mt-0.5">Válido até 18/08/2027</div>
          </div>

          <div className="p-3 bg-slate-800/40 rounded-lg border border-slate-700/50">
            <div className="text-slate-400 flex items-center gap-1.5 font-medium">
              <Clock className="w-3.5 h-3.5 text-cyan-400" />
              Última Verificação SEFAZ
            </div>
            <div className="font-bold text-slate-200 mt-1">{lastSyncTime}</div>
            <div className="text-[11px] text-slate-400 mt-0.5">Consulta periódica a cada 1 hora</div>
          </div>

          <div className="p-3 bg-slate-800/40 rounded-lg border border-slate-700/50">
            <div className="text-slate-400 flex items-center gap-1.5 font-medium">
              <Layers className="w-3.5 h-3.5 text-teal-400" />
              Último NSU Sincronizado
            </div>
            <div className="font-mono font-bold text-slate-200 mt-1">#{currentNsu}</div>
            <div className="text-[11px] text-slate-400 mt-0.5">Sequencial de controle Receita</div>
          </div>

          <div className="p-3 bg-slate-800/40 rounded-lg border border-slate-700/50">
            <div className="text-slate-400 flex items-center gap-1.5 font-medium">
              <FileSpreadsheet className="w-3.5 h-3.5 text-amber-400" />
              Volume no Período
            </div>
            <div className="font-bold text-white mt-1">
              R$ {totalValor.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
            </div>
            <div className="text-[11px] text-slate-400 mt-0.5">{notes.length} notas ({pendentesCount} pendentes)</div>
          </div>
        </div>

        {/* Feedback Alert */}
        {feedbackMsg && (
          <div className="mt-4 p-3 rounded-lg bg-emerald-950/40 border border-emerald-500/40 text-emerald-300 text-xs flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
            <span>{feedbackMsg}</span>
          </div>
        )}
      </div>

      {/* Captured Notes Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
        <div className="p-4 border-b border-slate-800 flex items-center justify-between text-xs">
          <span className="font-bold text-slate-200 flex items-center gap-2">
            <FileText className="w-4 h-4 text-emerald-400" />
            Notas Fiscais Eletrônicas Capturadas Automaticamente
          </span>
          <span className="text-slate-400 font-mono">
            {notes.length} documentos encontrados
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-800/70 text-slate-400 border-b border-slate-800 font-mono">
              <tr>
                <th className="py-2.5 px-3">NSU / NF-e</th>
                <th className="py-2.5 px-3">Emissão</th>
                <th className="py-2.5 px-3">Emitente (Fornecedor)</th>
                <th className="py-2.5 px-3">Chave de Acesso (44 dígitos)</th>
                <th className="py-2.5 px-3 text-right">Valor Total</th>
                <th className="py-2.5 px-3 text-center">Status Contábil</th>
                <th className="py-2.5 px-3 text-center">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {notes.map((n) => (
                <tr key={n.id} className="hover:bg-slate-800/30 transition-colors">
                  <td className="py-3 px-3 font-mono">
                    <span className="text-slate-500 text-[10px] block">NSU #{n.nsu}</span>
                    <span className="font-bold text-slate-200">NF-e {n.numero}</span>
                    <span className="text-[10px] text-slate-400 block">Série {n.serie}</span>
                  </td>
                  <td className="py-3 px-3 text-slate-300 font-mono text-[11px] whitespace-nowrap">
                    {n.dataEmissao}
                  </td>
                  <td className="py-3 px-3">
                    <div className="font-semibold text-slate-200 truncate max-w-xs">{n.razaoEmitente}</div>
                    <div className="font-mono text-slate-400 text-[11px]">{n.cnpjEmitente}</div>
                  </td>
                  <td className="py-3 px-3 font-mono text-[11px] text-slate-400 max-w-[220px] truncate" title={n.chaveAcesso}>
                    {n.chaveAcesso}
                  </td>
                  <td className="py-3 px-3 text-right font-mono font-bold text-emerald-400 whitespace-nowrap">
                    R$ {n.valorTotal.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                  </td>
                  <td className="py-3 px-3 text-center">
                    {n.conciliadoContabil ? (
                      <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        <Check className="w-3 h-3" />
                        Contabilizada
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
                        <Clock className="w-3 h-3" />
                        Pendente
                      </span>
                    )}
                  </td>
                  <td className="py-3 px-3 text-center whitespace-nowrap">
                    <div className="flex items-center justify-center gap-1.5">
                      <button
                        onClick={() => setSelectedNote(n)}
                        className="p-1.5 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors cursor-pointer"
                        title="Ver Detalhes do Documento Fiscal"
                      >
                        <Eye className="w-3.5 h-3.5" />
                      </button>

                      {!n.conciliadoContabil && (
                        <button
                          onClick={() => handleContabilizar(n.id)}
                          className="px-2.5 py-1 rounded-md bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 border border-emerald-500/30 text-[11px] font-semibold transition-colors cursor-pointer"
                          title="Gerar Partidas Dobradas"
                        >
                          Contabilizar
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Note Detail Modal */}
      {selectedNote && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full p-6 space-y-5 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <span className="text-[10px] font-mono uppercase text-emerald-400 font-bold">Documento Fiscal Eletrônico</span>
                <h3 className="text-lg font-bold text-white">NF-e #{selectedNote.numero} - Série {selectedNote.serie}</h3>
              </div>
              <button
                onClick={() => setSelectedNote(null)}
                className="text-slate-400 hover:text-white text-lg p-1"
              >
                &times;
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="p-3 bg-slate-800/40 rounded-lg">
                <span className="text-slate-500 block text-[10px]">EMITENTE</span>
                <span className="font-semibold text-slate-200">{selectedNote.razaoEmitente}</span>
                <span className="block font-mono text-slate-400">{selectedNote.cnpjEmitente}</span>
              </div>
              <div className="p-3 bg-slate-800/40 rounded-lg">
                <span className="text-slate-500 block text-[10px]">DESTINATÁRIO (CLIENTE)</span>
                <span className="font-semibold text-slate-200">{selectedNote.razaoDestinatario}</span>
                <span className="block font-mono text-slate-400">{selectedNote.cnpjDestinatario}</span>
              </div>
            </div>

            <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 font-mono text-xs">
              <span className="text-slate-500 block text-[10px] mb-1">CHAVE DE ACESSO (SEFAZ):</span>
              <span className="text-emerald-300 break-all">{selectedNote.chaveAcesso}</span>
            </div>

            <div className="grid grid-cols-4 gap-2 text-center text-xs font-mono">
              <div className="p-2 bg-slate-800/60 rounded">
                <span className="text-slate-400 block text-[10px]">VALOR TOTAL</span>
                <span className="font-bold text-white">R$ {selectedNote.valorTotal.toFixed(2)}</span>
              </div>
              <div className="p-2 bg-slate-800/60 rounded">
                <span className="text-slate-400 block text-[10px]">ICMS</span>
                <span className="font-bold text-slate-300">R$ {selectedNote.valorIcms.toFixed(2)}</span>
              </div>
              <div className="p-2 bg-slate-800/60 rounded">
                <span className="text-slate-400 block text-[10px]">PIS</span>
                <span className="font-bold text-slate-300">R$ {selectedNote.valorPis.toFixed(2)}</span>
              </div>
              <div className="p-2 bg-slate-800/60 rounded">
                <span className="text-slate-400 block text-[10px]">COFINS</span>
                <span className="font-bold text-slate-300">R$ {selectedNote.valorCofins.toFixed(2)}</span>
              </div>
            </div>

            {/* Partidas contábeis automáticas */}
            <div className="p-3 bg-emerald-950/20 border border-emerald-900/30 rounded-lg text-xs">
              <span className="font-bold text-emerald-400 block mb-1">Partidas Dobradas Geradas Automaticamente:</span>
              <div className="space-y-1 font-mono text-[11px]">
                <div className="flex justify-between text-slate-300">
                  <span>[D] 1.1.04.01.0001 - Estoque de Mercadorias para Revenda:</span>
                  <span className="text-emerald-400">R$ {(selectedNote.valorTotal - selectedNote.valorIcms - selectedNote.valorPis - selectedNote.valorCofins).toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-slate-300">
                  <span>[D] 1.1.03.02.0001 - Impostos a Recuperar (ICMS / PIS / COFINS):</span>
                  <span className="text-emerald-400">R$ {(selectedNote.valorIcms + selectedNote.valorPis + selectedNote.valorCofins).toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-slate-300 border-t border-slate-800 pt-1">
                  <span>[C] 2.1.01.01.0001 - Fornecedores Nacionais a Pagar:</span>
                  <span className="text-emerald-400">R$ {selectedNote.valorTotal.toFixed(2)}</span>
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setSelectedNote(null)}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold"
              >
                Fechar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
