import React, { useState } from 'react';
import { 
  Sparkles, 
  Bot, 
  FileCheck2, 
  CreditCard, 
  Users, 
  CalendarClock, 
  Layers, 
  Check, 
  ChevronRight,
  TrendingUp,
  ShieldAlert
} from 'lucide-react';
import { FEATURE_PROPOSALS } from '../data/blueprintData';
import { FeatureProposal } from '../types';

export const FeaturesTab: React.FC = () => {
  const [selectedCategory, setSelectedCategory] = useState<string>('Todas');
  const [activeFeatureId, setActiveFeatureId] = useState<string>(FEATURE_PROPOSALS[0].id);

  const categories = ['Todas', 'Fiscal', 'Contábil', 'Financeiro', 'Automação'];

  const filteredFeatures = FEATURE_PROPOSALS.filter(
    f => selectedCategory === 'Todas' || f.category === selectedCategory
  );

  const activeFeature = FEATURE_PROPOSALS.find(f => f.id === activeFeatureId) || FEATURE_PROPOSALS[0];

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 sm:p-6">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-cyan-500/10 text-cyan-400 rounded-xl border border-cyan-500/20">
            <Sparkles className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white tracking-tight">
              Novas Funcionalidades de Alto Valor para o UBJ Contábil
            </h2>
            <p className="text-xs sm:text-sm text-slate-400 mt-1">
              Diferenciais competitivos modernos para transformar o escritório contábil em um hub de inteligência e automação.
            </p>
          </div>
        </div>

        {/* Category Pills */}
        <div className="flex gap-2 mt-5 overflow-x-auto pb-1 text-xs">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-3 py-1.5 rounded-lg font-medium transition-colors cursor-pointer ${
                selectedCategory === cat
                  ? 'bg-cyan-600 text-white font-semibold'
                  : 'bg-slate-800 text-slate-400 hover:text-white'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Grid: Feature List & Deep Dive Card */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Feature List */}
        <div className="lg:col-span-5 space-y-3">
          {filteredFeatures.map((feat) => {
            const isSelected = feat.id === activeFeature.id;
            return (
              <div
                key={feat.id}
                onClick={() => setActiveFeatureId(feat.id)}
                className={`p-4 rounded-xl border transition-all cursor-pointer ${
                  isSelected
                    ? 'bg-cyan-950/25 border-cyan-500/60 shadow-md'
                    : 'bg-slate-900 border-slate-800 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded font-mono ${
                    feat.status === 'Essencial' 
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      : feat.status === 'Estratégica'
                      ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20'
                      : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                  }`}>
                    {feat.status.toUpperCase()}
                  </span>
                  <span className="text-[10px] font-mono text-slate-400 bg-slate-800 px-2 py-0.5 rounded">
                    Complexidade: {feat.complexity}
                  </span>
                </div>
                <h3 className={`text-sm font-bold mt-2 ${isSelected ? 'text-cyan-300' : 'text-slate-200'}`}>
                  {feat.title}
                </h3>
                <p className="text-xs text-slate-400 mt-1 line-clamp-2 leading-relaxed">
                  {feat.summary}
                </p>
              </div>
            );
          })}
        </div>

        {/* Right Column: Deep Dive */}
        <div className="lg:col-span-7 bg-slate-900 border border-slate-800 rounded-xl p-5 sm:p-7 space-y-6">
          <div>
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <span className="text-xs font-mono px-2.5 py-1 rounded bg-slate-800 text-cyan-400 border border-slate-700">
                Módulo: {activeFeature.category}
              </span>
              <span className="text-xs font-semibold px-2.5 py-1 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                {activeFeature.status}
              </span>
            </div>
            <h3 className="text-xl font-bold text-white mt-3">
              {activeFeature.title}
            </h3>
            <p className="text-sm text-slate-300 mt-2 leading-relaxed">
              {activeFeature.summary}
            </p>
          </div>

          {/* Business Value Box */}
          <div className="p-4 rounded-xl bg-gradient-to-r from-emerald-950/30 to-slate-800/40 border border-emerald-800/30">
            <h4 className="text-xs font-bold uppercase tracking-wider text-emerald-400 flex items-center gap-1.5 mb-1.5">
              <TrendingUp className="w-4 h-4" />
              Retorno sobre Investimento (Valor de Negócio para o Escritório)
            </h4>
            <p className="text-xs text-emerald-200/90 leading-relaxed font-sans">
              {activeFeature.businessValue}
            </p>
          </div>

          {/* Architecture Checklist */}
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5" />
              Etapas de Arquitetura & Implementação Técnica
            </h4>
            <div className="space-y-2">
              {activeFeature.architectureDetails.map((detail, idx) => (
                <div key={idx} className="flex items-start gap-2.5 p-3 rounded-lg bg-slate-800/40 border border-slate-800">
                  <span className="w-5 h-5 rounded-full bg-cyan-500/20 text-cyan-400 flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5">
                    {idx + 1}
                  </span>
                  <span className="text-xs text-slate-300 leading-relaxed">
                    {detail}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Tech Stack Pills */}
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
              Stack Tecnológica Recomendada
            </h4>
            <div className="flex flex-wrap gap-2">
              {activeFeature.techStack.map((tech, idx) => (
                <span key={idx} className="px-2.5 py-1 text-xs font-mono rounded-md bg-slate-800 text-slate-300 border border-slate-700">
                  {tech}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
