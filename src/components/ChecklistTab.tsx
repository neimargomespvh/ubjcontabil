import React, { useState } from 'react';
import { 
  CheckSquare, 
  Square, 
  Download, 
  Copy, 
  Check, 
  Filter, 
  ShieldCheck,
  Sparkles,
  AlertCircle
} from 'lucide-react';
import { INITIAL_CHECKLIST } from '../data/blueprintData';
import { AuditChecklistItem } from '../types';

export const ChecklistTab: React.FC = () => {
  const [items, setItems] = useState<AuditChecklistItem[]>(INITIAL_CHECKLIST);
  const [filterCategory, setFilterCategory] = useState<string>('Todas');
  const [copied, setCopied] = useState<boolean>(false);

  const categories = ['Todas', 'Banco de Dados', 'Performance', 'Funcionalidades', 'Compliance & Segurança'];

  const toggleItem = (id: string) => {
    setItems(prev => prev.map(item => 
      item.id === id ? { ...item, completed: !item.completed } : item
    ));
  };

  const filteredItems = items.filter(
    item => filterCategory === 'Todas' || item.category === filterCategory
  );

  const completedCount = items.filter(i => i.completed).length;
  const progressPercent = Math.round((completedCount / items.length) * 100);

  const generateMarkdownReport = () => {
    let md = `# RELATÓRIO DE AUDITORIA E IMPLEMENTAÇÃO - UBJ CONTÁBIL\n`;
    md += `Data: ${new Date().toLocaleDateString('pt-BR')}\n`;
    md += `Progresso Geral: ${completedCount}/${items.length} itens (${progressPercent}%)\n\n`;

    categories.filter(c => c !== 'Todas').forEach(cat => {
      md += `## ${cat}\n`;
      items.filter(i => i.category === cat).forEach(item => {
        md += `- [${item.completed ? 'x' : ' '}] **${item.title}** (Impacto: ${item.impact})\n`;
        md += `  _${item.description}_\n`;
      });
      md += `\n`;
    });

    return md;
  };

  const handleCopyReport = () => {
    navigator.clipboard.writeText(generateMarkdownReport());
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadMarkdown = () => {
    const blob = new Blob([generateMarkdownReport()], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'auditoria_ubj_contabil_checklist.md';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 sm:p-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-emerald-500/10 text-emerald-400 rounded-xl border border-emerald-500/20">
              <CheckSquare className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white tracking-tight">
                Checklist de Modernização & Governança Técnica
              </h2>
              <p className="text-xs sm:text-sm text-slate-400 mt-0.5">
                Roteiro de tarefas prioritárias para adequação do banco de dados, performance e funcionalidades.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 self-start sm:self-auto">
            <button
              onClick={handleCopyReport}
              className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 transition-colors flex items-center gap-1.5 text-xs font-medium cursor-pointer"
              title="Copiar relatório em Markdown"
            >
              {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
              <span className="hidden sm:inline">{copied ? 'Copiado!' : 'Copiar Relatório'}</span>
            </button>

            <button
              onClick={handleDownloadMarkdown}
              className="p-2 rounded-lg bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 border border-emerald-500/30 transition-colors flex items-center gap-1.5 text-xs font-medium cursor-pointer"
              title="Baixar checklist em .md"
            >
              <Download className="w-4 h-4" />
              <span className="hidden sm:inline">Baixar .md</span>
            </button>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="mt-6 pt-5 border-t border-slate-800">
          <div className="flex justify-between items-center text-xs mb-2">
            <span className="text-slate-300 font-semibold">
              Taxa de Adequação Técnica: {completedCount} de {items.length} itens concluídos
            </span>
            <span className="font-mono font-bold text-emerald-400">{progressPercent}%</span>
          </div>
          <div className="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden">
            <div 
              className="bg-gradient-to-r from-emerald-500 to-teal-400 h-2.5 rounded-full transition-all duration-500"
              style={{ width: `${progressPercent}%` }}
            ></div>
          </div>
        </div>

        {/* Category Filter */}
        <div className="flex gap-2 mt-5 overflow-x-auto pb-1 text-xs">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setFilterCategory(cat)}
              className={`px-3 py-1.5 rounded-lg font-medium transition-colors cursor-pointer ${
                filterCategory === cat
                  ? 'bg-emerald-600 text-white font-semibold'
                  : 'bg-slate-800 text-slate-400 hover:text-white'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Checklist Items */}
      <div className="space-y-3">
        {filteredItems.map((item) => (
          <div
            key={item.id}
            onClick={() => toggleItem(item.id)}
            className={`p-4 rounded-xl border transition-all cursor-pointer flex items-start gap-3 ${
              item.completed 
                ? 'bg-emerald-950/15 border-emerald-500/30 text-slate-300' 
                : 'bg-slate-900 border-slate-800 hover:border-slate-700'
            }`}
          >
            <div className="mt-0.5 text-emerald-400 shrink-0">
              {item.completed ? (
                <CheckSquare className="w-5 h-5 fill-emerald-500/20" />
              ) : (
                <Square className="w-5 h-5 text-slate-500 hover:text-slate-400" />
              )}
            </div>

            <div className="flex-1">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <div className="flex items-center gap-2">
                  <h3 className={`text-sm font-bold ${item.completed ? 'text-slate-200 line-through decoration-slate-500' : 'text-white'}`}>
                    {item.title}
                  </h3>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                    {item.category}
                  </span>
                </div>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded font-mono ${
                  item.impact === 'Crítica'
                    ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                    : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                }`}>
                  IMPACTO {item.impact.toUpperCase()}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                {item.description}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
