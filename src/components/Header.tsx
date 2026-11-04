import React from 'react';
import { 
  Building2, 
  Database, 
  Zap, 
  Sparkles, 
  Activity, 
  Code2, 
  CheckSquare, 
  Layers
} from 'lucide-react';
import { ActiveTab } from '../types';

interface HeaderProps {
  activeTab: ActiveTab;
  onTabChange: (tab: ActiveTab) => void;
}

export const Header: React.FC<HeaderProps> = ({ activeTab, onTabChange }) => {
  const navItems: { id: ActiveTab; label: string; icon: React.ComponentType<{ className?: string }>; badge?: string }[] = [
    { id: 'overview', label: 'Visão Geral', icon: Layers },
    { id: 'dfe', label: 'Robô DFe SEFAZ', icon: Sparkles, badge: 'Novo' },
    { id: 'monofasico', label: 'Segregação Monofásica', icon: Zap, badge: 'Novo' },
    { id: 'conciliador', label: 'Conciliador OFX', icon: Activity, badge: 'Novo' },
    { id: 'scripts', label: 'Setup Local & Git', icon: Code2, badge: 'Script' },
    { id: 'database', label: 'Banco de Dados (DDL)', icon: Database },
    { id: 'performance', label: 'Performance', icon: Zap },
    { id: 'features', label: 'Roadmap Completo', icon: Sparkles },
    { id: 'profiler', label: 'Simulador de Carga', icon: Activity },
    { id: 'auditor', label: 'Analisador de Código', icon: Code2 },
    { id: 'checklist', label: 'Checklist', icon: CheckSquare },
  ];

  return (
    <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur-md sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row md:items-center justify-between py-4 gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-700 flex items-center justify-center shadow-lg shadow-emerald-900/30 text-white font-bold text-lg">
              <Building2 className="w-5 h-5 text-emerald-100" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold text-slate-100 tracking-tight">
                  UBJ Contábil
                </h1>
                <span className="text-[11px] font-semibold uppercase px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  Auditoria & Arquitetura
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Otimização de Banco de Dados, Performance e Funcionalidades para Sistemas Contábeis e Fiscais
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 self-start md:self-auto text-xs text-slate-400">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-800 border border-slate-700">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              PostgreSQL 17+ Ready
            </span>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-800 border border-slate-700">
              ECD / ECF / SPED Compliance
            </span>
          </div>
        </div>

        {/* Tab Navigation */}
        <nav className="flex space-x-1 overflow-x-auto py-2 scrollbar-thin scrollbar-thumb-slate-700">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onTabChange(item.id)}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs sm:text-sm font-medium transition-all whitespace-nowrap cursor-pointer ${
                  isActive
                    ? 'bg-emerald-600 text-white shadow-md shadow-emerald-950/40 font-semibold'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-slate-400'}`} />
                <span>{item.label}</span>
                {item.badge && (
                  <span className={`text-[9px] font-mono px-1.5 py-0.2 rounded font-bold uppercase ${
                    isActive 
                      ? 'bg-emerald-950/80 text-emerald-200 border border-emerald-400/40' 
                      : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                  }`}>
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>
    </header>
  );
};
