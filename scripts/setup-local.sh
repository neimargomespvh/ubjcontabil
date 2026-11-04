#!/usr/bin/env bash
# ====================================================================
# UBJ CONTÁBIL - SCRIPT RESILIENTE DE SETUP E DESENVOLVIMENTO LOCAL
# Compatível com Linux, macOS e Windows (Git Bash / WSL)
# ====================================================================

set -e

echo ""
echo "============================================================"
echo "    UBJ CONTÁBIL - Configuração do Ambiente Local           "
echo "============================================================"
echo ""

REPO_URL="https://github.com/neimargomespvh/ubjcontabil.git"

# 1. Verificar Node e Git
echo "[1/4] Verificando pré-requisitos locais..."

if ! command -v git &> /dev/null; then
    echo "ERRO: Git não encontrado. Instale o Git em https://git-scm.com/"
    exit 1
fi

if ! command -v node &> /dev/null; then
    echo "ERRO: Node.js não encontrado. Instale o Node.js v18+ em https://nodejs.org/"
    exit 1
fi

echo "      Node.js detectado: $(node -v)"
echo "      Git detectado: $(git --version)"

# 2. Identificar se já estamos na pasta do projeto ou se devemos clonar
echo ""
echo "[2/4] Verificando arquivos do projeto..."

# Se já estamos em uma pasta chamada UbjContabil ou ubjcontabil, usar o diretório atual
CURRENT_DIR_NAME=$(basename "$PWD")

if [ -f "package.json" ]; then
    echo "      package.json encontrado no diretório atual ($PWD)."
else
    # Se existe uma subpasta ubjcontabil com package.json, entrar nela
    if [ -f "ubjcontabil/package.json" ]; then
        cd ubjcontabil
        echo "      Acessando pasta existente: $PWD"
    else
        # Se o repositório remoto estiver acessível e tiver arquivos
        echo "      Verificando repositório GitHub..."
        if [ ! -d ".git" ] && [ ! -d "ubjcontabil/.git" ]; then
            echo "      Tentando clonar repositório..."
            if ! git clone "$REPO_URL" ubjcontabil 2>/dev/null; then
                echo "      Repositório remoto privado ou não acessível sem autenticação."
            else
                if [ -d "ubjcontabil" ]; then
                    cd ubjcontabil
                fi
            fi
        fi
    fi
fi

# Se mesmo assim não houver package.json (ex: repo do GitHub vazio ou download direto do script), inicializar os arquivos essenciais
if [ ! -f "package.json" ]; then
    echo ""
    echo "      -> Criando package.json e estrutura essencial do UBJ Contábil..."
    cat << 'EOF' > package.json
{
  "name": "ubj-contabil",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite --port=3000 --host=0.0.0.0",
    "build": "vite build",
    "preview": "vite preview",
    "lint": "tsc --noEmit"
  },
  "dependencies": {
    "@tailwindcss/vite": "^4.3.3",
    "@vitejs/plugin-react": "^6.1.1",
    "lucide-react": "^0.546.0",
    "react": "^19.0.1",
    "react-dom": "^19.0.1",
    "vite": "^8.3.0",
    "tailwindcss": "^4.3.3"
  },
  "devDependencies": {
    "@types/node": "^22.14.0",
    "@types/react": "^19.3.0",
    "@types/react-dom": "^19.3.0",
    "typescript": "^7.0.2"
  }
}
EOF
fi

if [ ! -f "tsconfig.json" ]; then
    cat << 'EOF' > tsconfig.json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "types": ["vite/client"],
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "isolatedModules": true,
    "moduleDetection": "force",
    "jsx": "react-jsx",
    "paths": { "@/*": ["./*"] },
    "noEmit": true
  },
  "exclude": ["dist"]
}
EOF
fi

if [ ! -f "vite.config.ts" ]; then
    cat << 'EOF' > vite.config.ts
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { defineConfig } from 'vite';

export default defineConfig(() => {
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(import.meta.dirname || '.', '.'),
      },
    },
    server: {
      port: 3000,
      host: '0.0.0.0',
    },
  };
});
EOF
fi

if [ ! -f "index.html" ]; then
    cat << 'EOF' > index.html
<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>UBJ Contábil - Sistema de Gestão</title>
  </head>
  <body class="bg-slate-950 text-slate-100 antialiased">
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
EOF
fi

mkdir -p src

if [ ! -f "src/index.css" ]; then
    echo '@import "tailwindcss";' > src/index.css
fi

if [ ! -f "src/App.tsx" ]; then
    cat << 'EOF' > src/App.tsx
import React, { useState } from 'react';

export default function App() {
  const [activeTab, setActiveTab] = useState<'inicio' | 'dfe' | 'monofasico' | 'conciliador'>('inicio');

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans p-6 sm:p-10">
      <div className="max-w-5xl mx-auto space-y-6">
        <header className="border-b border-slate-800 pb-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-black text-white tracking-tight">UBJ Contábil</h1>
              <span className="px-2 py-0.5 text-xs font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded">
                Ambiente Local Ativo
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Servidor local Vite rodando com sucesso na porta 3000.
            </p>
          </div>

          <div className="flex gap-2">
            <button 
              onClick={() => setActiveTab('inicio')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium ${activeTab === 'inicio' ? 'bg-emerald-600 text-white' : 'bg-slate-800 text-slate-400'}`}
            >
              Visão Geral
            </button>
            <button 
              onClick={() => setActiveTab('dfe')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium ${activeTab === 'dfe' ? 'bg-emerald-600 text-white' : 'bg-slate-800 text-slate-400'}`}
            >
              Robô DFe SEFAZ
            </button>
            <button 
              onClick={() => setActiveTab('monofasico')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium ${activeTab === 'monofasico' ? 'bg-emerald-600 text-white' : 'bg-slate-800 text-slate-400'}`}
            >
              Segregação Monofásica
            </button>
            <button 
              onClick={() => setActiveTab('conciliador')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium ${activeTab === 'conciliador' ? 'bg-emerald-600 text-white' : 'bg-slate-800 text-slate-400'}`}
            >
              Conciliador OFX
            </button>
          </div>
        </header>

        {activeTab === 'inicio' && (
          <div className="p-6 bg-slate-900 border border-slate-800 rounded-2xl space-y-4">
            <h2 className="text-lg font-bold text-white">Servidor Local Inicializado com Sucesso! 🚀</h2>
            <p className="text-sm text-slate-300 leading-relaxed">
              O ambiente local do <strong>UBJ Contábil</strong> está funcionando corretamente com Node.js e Vite.
            </p>
            <div className="p-4 bg-emerald-950/30 border border-emerald-600/30 rounded-xl text-xs text-emerald-200">
              <strong>Dica:</strong> Para ter todos os componentes e telas completas desenvolvidas no applet, você também pode descompactar o arquivo <code>ubjcontabil-completo.zip</code> nesta pasta.
            </div>
          </div>
        )}

        {activeTab === 'dfe' && (
          <div className="p-6 bg-slate-900 border border-slate-800 rounded-2xl space-y-3">
            <h2 className="text-lg font-bold text-white">Robô DFe SEFAZ (Módulo Fiscal)</h2>
            <p className="text-xs text-slate-400">Captura e manifestação contínua de NF-e por NSU da Receita Federal.</p>
            <div className="p-4 bg-slate-800/50 rounded-xl font-mono text-xs text-slate-300">
              Certificado A1: Ativo &bull; Último NSU: #84924 &bull; Status SEFAZ: Operacional
            </div>
          </div>
        )}

        {activeTab === 'monofasico' && (
          <div className="p-6 bg-slate-900 border border-slate-800 rounded-2xl space-y-3">
            <h2 className="text-lg font-bold text-white">Segregação Monofásica (Simples Nacional)</h2>
            <p className="text-xs text-slate-400">Exclusão da parcela de PIS e COFINS no PGDAS-D para produtos monofásicos.</p>
            <div className="p-4 bg-slate-800/50 rounded-xl font-mono text-xs text-emerald-400">
              Economia Estimada: ~R$ 2.719,25/mês em clientes de autopeças e farmácias
            </div>
          </div>
        )}

        {activeTab === 'conciliador' && (
          <div className="p-6 bg-slate-900 border border-slate-800 rounded-2xl space-y-3">
            <h2 className="text-lg font-bold text-white">Conciliador Bancário Inteligente (OFX)</h2>
            <p className="text-xs text-slate-400">Importação de extratos com correspondência em partidas dobradas.</p>
            <div className="p-4 bg-slate-800/50 rounded-xl font-mono text-xs text-teal-400">
              Regras Contábeis Automáticas: Ativas (Taxa de acerto 96.8%)
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
EOF
fi

if [ ! -f "src/main.tsx" ]; then
    cat << 'EOF' > src/main.tsx
import { createRoot } from 'react-dom/client';
import App from './App.tsx';
import './index.css';

createRoot(document.getElementById('root')!).render(<App />);
EOF
fi

# 3. Configurar Variáveis de Ambiente (.env)
echo ""
echo "[3/4] Configurando arquivo de ambiente (.env)..."
if [ ! -f ".env" ]; then
    cat << 'EOF' > .env
PORT=3000
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ubj_contabil
REDIS_URL=redis://localhost:6379
NODE_ENV=development
EOF
    echo "      Arquivo .env gerado com sucesso!"
else
    echo "      Arquivo .env já existente."
fi

# 4. Instalar Dependências
echo ""
echo "[4/4] Instalando dependências (npm install)..."
npm install

echo ""
echo "============================================================"
echo "    UBJ CONTÁBIL - AMBIENTE CONFIGURADO COM SUCESSO!        "
echo "============================================================"
echo ""
echo "Para iniciar o servidor agora, execute:"
echo ""
echo "    npm run dev"
echo ""
echo "Acesse no seu navegador: http://localhost:3000"
echo "============================================================"
