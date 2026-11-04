import React, { useState } from 'react';
import { AlertCircle, Lock, Key, Copy, Check, ExternalLink, ChevronDown, ChevronUp, ShieldCheck } from 'lucide-react';

export const RepoAlertBanner: React.FC = () => {
  const [copied, setCopied] = useState(false);
  const [isOpen, setIsOpen] = useState(false);

  const copyUrl = () => {
    navigator.clipboard.writeText('https://github.com/neimargomespvh/ubjcontabil.git');
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="bg-amber-950/40 border border-amber-600/30 rounded-xl p-4 sm:p-5 shadow-sm text-amber-100">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="p-2 bg-amber-500/20 text-amber-400 rounded-lg mt-0.5">
            <Lock className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="font-semibold text-amber-200 text-base">
                Repositório GitHub Privado / Protegido
              </h3>
              <span className="px-2 py-0.5 text-xs font-mono bg-amber-900/60 text-amber-300 border border-amber-700/50 rounded">
                neimargomespvh/ubjcontabil
              </span>
            </div>
            <p className="text-sm text-amber-200/90 mt-1 leading-relaxed">
              O repositório está privado no GitHub (retorno HTTP 404 / autenticação obrigatória ao clonar). 
              Para auxiliá-lo com excelência máxima, construímos esta <strong>Plataforma Completa de Diagnóstico & Blueprint Arquitetural</strong> específica para sistemas contábeis brasileiros, e disponibilizamos um <strong>Analisador de Código Interativo</strong> para você colar ou testar trechos do seu projeto!
            </p>
          </div>
        </div>
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="text-amber-300 hover:text-amber-100 p-1.5 rounded-lg hover:bg-amber-900/40 transition-colors flex items-center gap-1 text-xs font-medium whitespace-nowrap"
          title="Ver instruções de acesso"
        >
          {isOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          <span className="hidden sm:inline">{isOpen ? 'Ocultar Dicas' : 'Como Conectar'}</span>
        </button>
      </div>

      {isOpen && (
        <div className="mt-4 pt-4 border-t border-amber-700/30 grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
          <div className="p-3 bg-amber-900/25 rounded-lg border border-amber-800/40">
            <span className="font-semibold text-amber-200 flex items-center gap-1.5 mb-1.5">
              <span className="w-4 h-4 rounded-full bg-amber-500/30 text-amber-300 flex items-center justify-center text-[10px] font-bold">1</span>
              Usar Analisador de Código
            </span>
            <p className="text-amber-200/80 leading-relaxed">
              Vá na aba <strong>Analisador de Código & SQL</strong> deste applet para colar seus schemas (Prisma, DDL SQL, Drizzle) ou controllers e receber sugestões instantâneas.
            </p>
          </div>

          <div className="p-3 bg-amber-900/25 rounded-lg border border-amber-800/40">
            <span className="font-semibold text-amber-200 flex items-center gap-1.5 mb-1.5">
              <span className="w-4 h-4 rounded-full bg-amber-500/30 text-amber-300 flex items-center justify-center text-[10px] font-bold">2</span>
              Tornar Público no GitHub
            </span>
            <p className="text-amber-200/80 leading-relaxed">
              No GitHub: acesse <em>Settings</em> &gt; <em>Danger Zone</em> &gt; <em>Change visibility</em> &gt; <em>Make public</em>. Depois, avise no chat para clonarmos diretamente.
            </p>
          </div>

          <div className="p-3 bg-amber-900/25 rounded-lg border border-amber-800/40">
            <span className="font-semibold text-amber-200 flex items-center gap-1.5 mb-1.5">
              <span className="w-4 h-4 rounded-full bg-amber-500/30 text-amber-300 flex items-center justify-center text-[10px] font-bold">3</span>
              Adotar o Blueprint Pronto
            </span>
            <p className="text-amber-200/80 leading-relaxed">
              Você pode copiar todo o DDL PostgreSQL e padrões de performance disponibilizados nas abas abaixo e aplicá-los diretamente no seu sistema UBJ Contábil.
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
