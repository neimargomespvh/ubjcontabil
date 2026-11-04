/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { ActiveTab } from './types';
import { Header } from './components/Header';
import { RepoAlertBanner } from './components/RepoAlertBanner';
import { OverviewTab } from './components/OverviewTab';
import { DatabaseSchemaTab } from './components/DatabaseSchemaTab';
import { PerformanceTab } from './components/PerformanceTab';
import { FeaturesTab } from './components/FeaturesTab';
import { DfeSefazModule } from './components/DfeSefazModule';
import { MonofasicoAuditModule } from './components/MonofasicoAuditModule';
import { BankReconciliationModule } from './components/BankReconciliationModule';
import { LocalDevScriptsTab } from './components/LocalDevScriptsTab';
import { QueryProfilerSim } from './components/QueryProfilerSim';
import { CodeAuditorTab } from './components/CodeAuditorTab';
import { ChecklistTab } from './components/ChecklistTab';
import { Building2, ShieldCheck } from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('overview');

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-emerald-500 selection:text-white">
      {/* Top Header */}
      <Header activeTab={activeTab} onTabChange={setActiveTab} />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Repository Visibility Alert Banner */}
        <RepoAlertBanner />

        {/* Tab View Router */}
        {activeTab === 'overview' && (
          <OverviewTab onNavigate={(tab) => setActiveTab(tab)} />
        )}

        {/* 3 Strategic Interactive Modules */}
        {activeTab === 'dfe' && (
          <DfeSefazModule />
        )}

        {activeTab === 'monofasico' && (
          <MonofasicoAuditModule />
        )}

        {activeTab === 'conciliador' && (
          <BankReconciliationModule />
        )}

        {/* Local Setup & Git Sync Scripts */}
        {activeTab === 'scripts' && (
          <LocalDevScriptsTab />
        )}

        {activeTab === 'database' && (
          <DatabaseSchemaTab />
        )}

        {activeTab === 'performance' && (
          <PerformanceTab />
        )}

        {activeTab === 'features' && (
          <FeaturesTab />
        )}

        {activeTab === 'profiler' && (
          <QueryProfilerSim />
        )}

        {activeTab === 'auditor' && (
          <CodeAuditorTab />
        )}

        {activeTab === 'checklist' && (
          <ChecklistTab />
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-slate-950/80 py-6 mt-12 text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Building2 className="w-4 h-4 text-emerald-500" />
            <span className="font-semibold text-slate-400">UBJ Contábil</span>
            <span>&bull;</span>
            <span>Arquitetura de Alta Concorrência para Sistemas Fiscais e Contábeis</span>
          </div>

          <div className="flex items-center gap-4 text-slate-400">
            <span className="flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
              ITG 2000 (R1) & CFC Compliant
            </span>
            <span>&bull;</span>
            <span>SPED ECD / ECF Ready</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
