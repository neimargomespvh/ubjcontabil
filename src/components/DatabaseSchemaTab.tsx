import React, { useState } from 'react';
import { 
  Database, 
  Copy, 
  Check, 
  Download, 
  Key, 
  Link as LinkIcon, 
  Layers, 
  Table as TableIcon,
  Search,
  Sparkles,
  Info
} from 'lucide-react';
import { DATABASE_TABLES, SQL_DDL_PROPOSAL } from '../data/blueprintData';
import { DatabaseTable } from '../types';

export const DatabaseSchemaTab: React.FC = () => {
  const [viewMode, setViewMode] = useState<'explorer' | 'ddl'>('explorer');
  const [selectedTableId, setSelectedTableId] = useState<string>('lancamentos_contabeis');
  const [schemaFilter, setSchemaFilter] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [copied, setCopied] = useState(false);

  const filteredTables = DATABASE_TABLES.filter(t => {
    const matchesSchema = schemaFilter === 'all' || t.schema === schemaFilter;
    const matchesSearch = t.name.toLowerCase().includes(searchTerm.toLowerCase()) || 
                          t.description.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesSchema && matchesSearch;
  });

  const selectedTable = DATABASE_TABLES.find(t => t.id === selectedTableId) || DATABASE_TABLES[0];

  const handleCopy = () => {
    navigator.clipboard.writeText(SQL_DDL_PROPOSAL);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadSql = () => {
    const blob = new Blob([SQL_DDL_PROPOSAL], { type: 'text/sql' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'ubj_contabil_schema_postgresql.sql';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      {/* Header with View Toggle and Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900 border border-slate-800 p-4 rounded-xl">
        <div>
          <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
            <Database className="w-5 h-5 text-emerald-400" />
            Modelagem Relacional de Banco de Dados (PostgreSQL)
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Arquitetura multitenant com validação estrita de partidas dobradas e compatibilidade SPED.
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <div className="flex bg-slate-800 p-1 rounded-lg border border-slate-700 text-xs font-medium">
            <button
              onClick={() => setViewMode('explorer')}
              className={`px-3 py-1.5 rounded-md transition-colors cursor-pointer ${
                viewMode === 'explorer' ? 'bg-emerald-600 text-white font-semibold' : 'text-slate-400 hover:text-white'
              }`}
            >
              Explorador de Entidades
            </button>
            <button
              onClick={() => setViewMode('ddl')}
              className={`px-3 py-1.5 rounded-md transition-colors cursor-pointer ${
                viewMode === 'ddl' ? 'bg-emerald-600 text-white font-semibold' : 'text-slate-400 hover:text-white'
              }`}
            >
              Script SQL (DDL)
            </button>
          </div>

          <button
            onClick={handleCopy}
            className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 transition-colors flex items-center gap-1.5 text-xs cursor-pointer"
            title="Copiar DDL SQL"
          >
            {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
            <span className="hidden md:inline">{copied ? 'Copiado!' : 'Copiar DDL'}</span>
          </button>

          <button
            onClick={handleDownloadSql}
            className="p-2 rounded-lg bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 border border-emerald-500/30 transition-colors flex items-center gap-1.5 text-xs font-medium cursor-pointer"
            title="Download arquivo .sql"
          >
            <Download className="w-4 h-4" />
            <span className="hidden md:inline">Baixar .sql</span>
          </button>
        </div>
      </div>

      {viewMode === 'explorer' ? (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Table List / Navigation Column */}
          <div className="lg:col-span-4 space-y-3">
            {/* Search and Filters */}
            <div className="space-y-2">
              <div className="relative">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                <input
                  type="text"
                  placeholder="Filtrar tabelas..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div className="flex gap-1 overflow-x-auto pb-1 text-xs">
                {['all', 'core', 'contabil', 'fiscal'].map((schema) => (
                  <button
                    key={schema}
                    onClick={() => setSchemaFilter(schema)}
                    className={`px-2.5 py-1 rounded-md text-[11px] font-medium uppercase transition-colors cursor-pointer ${
                      schemaFilter === schema
                        ? 'bg-slate-700 text-emerald-400 font-bold border border-slate-600'
                        : 'bg-slate-900/60 text-slate-400 hover:text-slate-200 border border-slate-800'
                    }`}
                  >
                    {schema === 'all' ? 'Todos os Schemas' : schema}
                  </button>
                ))}
              </div>
            </div>

            {/* Tables Cards */}
            <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
              {filteredTables.map((table) => {
                const isSelected = table.id === selectedTable.id;
                return (
                  <div
                    key={table.id}
                    onClick={() => setSelectedTableId(table.id)}
                    className={`p-3 rounded-xl border transition-all cursor-pointer ${
                      isSelected
                        ? 'bg-emerald-950/20 border-emerald-500/60 shadow-sm'
                        : 'bg-slate-900 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <TableIcon className={`w-4 h-4 ${isSelected ? 'text-emerald-400' : 'text-slate-400'}`} />
                        <span className="font-mono text-xs font-bold text-slate-200">
                          {table.schema}.<span className={isSelected ? 'text-emerald-400' : ''}>{table.name}</span>
                        </span>
                      </div>
                      <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                        {table.columns.length} cols
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-1 line-clamp-2 leading-relaxed">
                      {table.description}
                    </p>
                    {table.partitionStrategy && (
                      <span className="inline-block mt-2 text-[10px] font-mono px-1.5 py-0.5 rounded bg-teal-950/60 text-teal-400 border border-teal-800/40">
                        ⚡ {table.partitionStrategy}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Table Details Column */}
          <div className="lg:col-span-8 bg-slate-900 border border-slate-800 rounded-xl p-5 sm:p-6 space-y-6">
            <div>
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 text-xs font-mono rounded bg-slate-800 text-slate-400 border border-slate-700">
                    Schema: {selectedTable.schema}
                  </span>
                  <h3 className="font-mono text-lg font-bold text-white">
                    {selectedTable.schema}.{selectedTable.name}
                  </h3>
                </div>
                {selectedTable.partitionStrategy && (
                  <span className="px-2.5 py-1 text-xs font-mono rounded-md bg-teal-500/10 text-teal-400 border border-teal-500/30">
                    ⚡ Particionada: {selectedTable.partitionStrategy}
                  </span>
                )}
              </div>
              <p className="text-xs sm:text-sm text-slate-300 mt-2 leading-relaxed">
                {selectedTable.description}
              </p>
            </div>

            {/* Column List */}
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5" />
                Estrutura de Colunas e Constraints
              </h4>
              <div className="overflow-x-auto border border-slate-800 rounded-lg">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-800/70 text-slate-400 border-b border-slate-800 font-mono">
                    <tr>
                      <th className="py-2.5 px-3">Coluna</th>
                      <th className="py-2.5 px-3">Tipo</th>
                      <th className="py-2.5 px-3">Constraints</th>
                      <th className="py-2.5 px-3">Finalidade Contábil / Regra</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800 font-mono">
                    {selectedTable.columns.map((col) => (
                      <tr key={col.name} className="hover:bg-slate-800/30">
                        <td className="py-2.5 px-3 font-semibold text-slate-200 flex items-center gap-1.5">
                          {col.isPrimary && <span title="Chave Primária"><Key className="w-3 h-3 text-amber-400" /></span>}
                          {col.isForeign && <span title={`Foreign Key: ${col.references}`}><LinkIcon className="w-3 h-3 text-cyan-400" /></span>}
                          {col.name}
                        </td>
                        <td className="py-2.5 px-3 text-emerald-400">{col.type}</td>
                        <td className="py-2.5 px-3 text-slate-400 text-[11px]">{col.constraints || '-'}</td>
                        <td className="py-2.5 px-3 font-sans text-slate-300 text-[11px] leading-relaxed">
                          {col.description}
                          {col.references && (
                            <span className="block text-[10px] font-mono text-cyan-400 mt-0.5">
                              &rarr; {col.references}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Indexes */}
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5" />
                Índices Otimizados de Alta Performance
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {selectedTable.indexes.map((idx) => (
                  <div key={idx.name} className="p-3 bg-slate-800/40 border border-slate-800 rounded-lg">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-bold text-emerald-400">{idx.name}</span>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-700 text-slate-300">
                        {idx.type}
                      </span>
                    </div>
                    <div className="font-mono text-[11px] text-slate-400 mt-1">
                      ({idx.columns.join(', ')})
                    </div>
                    <p className="text-xs text-slate-400 mt-1.5 font-sans leading-relaxed">
                      {idx.description}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* DDL SQL Viewer */
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-lg">
          <div className="bg-slate-800/80 px-4 py-3 border-b border-slate-800 flex items-center justify-between text-xs font-mono text-slate-400">
            <span>schema_postgresql_ubjcontabil.sql</span>
            <span>PostgreSQL 15+ / 17+</span>
          </div>
          <pre className="p-4 sm:p-6 text-xs sm:text-sm font-mono text-emerald-300/90 overflow-x-auto leading-relaxed bg-slate-950">
            <code>{SQL_DDL_PROPOSAL}</code>
          </pre>
        </div>
      )}
    </div>
  );
};
