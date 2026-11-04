import React, { useState } from 'react';
import { 
  Terminal, 
  Download, 
  Copy, 
  Check, 
  GitBranch, 
  Laptop, 
  ExternalLink, 
  Key, 
  ShieldCheck, 
  Sparkles, 
  RefreshCw,
  FolderDown,
  UploadCloud,
  FileArchive,
  AlertTriangle,
  CheckCircle2
} from 'lucide-react';
import { generateProjectZip } from '../utils/projectZip';

const SCRIPT_SETUP_SH = `#!/usr/bin/env bash
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

if ! command -v node &> /dev/null; then
    echo "ERRO: Node.js não encontrado. Instale o Node.js v18+ em https://nodejs.org/"
    exit 1
fi

echo "      Node.js detectado: $(node -v)"
echo "      Git detectado: $(git --version 2>/dev/null || echo 'instalado')"

# 2. Identificar se já estamos na pasta do projeto
echo ""
echo "[2/4] Verificando arquivos do projeto..."

# Se já houver subpasta ubjcontabil com package.json, entrar nela
if [ ! -f "package.json" ] && [ -f "ubjcontabil/package.json" ]; then
    cd ubjcontabil
fi

# Se não houver package.json (ex: repositório GitHub ainda vazio ou download avulso do script),
# inicializar a estrutura completa do UBJ Contábil automaticamente:
if [ ! -f "package.json" ]; then
    echo "      -> Gerando package.json e estrutura do UBJ Contábil..."
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
      alias: { '@': path.resolve(__dirname, '.') },
    },
    server: { port: 3000, host: '0.0.0.0' },
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
    <title>UBJ Contábil</title>
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
  const [tab, setTab] = useState('inicio');
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans p-6 sm:p-10">
      <div className="max-w-5xl mx-auto space-y-6">
        <header className="border-b border-slate-800 pb-4 flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-black text-white">UBJ Contábil</h1>
            <p className="text-xs text-slate-400">Servidor local Vite rodando na porta 3000</p>
          </div>
          <div className="flex gap-2">
            <button onClick={() => setTab('inicio')} className="px-3 py-1.5 rounded-lg text-xs bg-emerald-600 text-white">Visão Geral</button>
            <button onClick={() => setTab('dfe')} className="px-3 py-1.5 rounded-lg text-xs bg-slate-800 text-slate-400">Robô DFe SEFAZ</button>
            <button onClick={() => setTab('monofasico')} className="px-3 py-1.5 rounded-lg text-xs bg-slate-800 text-slate-400">Segregação Monofásica</button>
            <button onClick={() => setTab('conciliador')} className="px-3 py-1.5 rounded-lg text-xs bg-slate-800 text-slate-400">Conciliador OFX</button>
          </div>
        </header>
        <div className="p-6 bg-slate-900 border border-slate-800 rounded-2xl">
          <h2 className="text-lg font-bold text-white mb-2">Ambiente Local Ativo 🚀</h2>
          <p className="text-sm text-slate-300">Para carregar todos os módulos completos do applet, descompacte o arquivo <code>ubjcontabil-completo.zip</code> nesta pasta.</p>
        </div>
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
    echo "      Arquivo .env criado!"
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
echo "Para iniciar o servidor de desenvolvimento local, execute:"
echo ""
echo "    npm run dev"
echo ""
echo "Acesse a aplicação no navegador em: http://localhost:3000"
echo "============================================================"`;

const SCRIPT_SETUP_BAT = `@echo off
REM ====================================================================
REM UBJ CONTÁBIL - SCRIPT RESILIENTE DE SETUP LOCAL (WINDOWS)
REM ====================================================================

echo ============================================================
echo     UBJ CONTABIL - Configuracao do Ambiente Local (Windows)
echo ============================================================
echo.

where node >nul 2>nul
if %errorlevel% neq 0 (
    echo ERRO: Node.js nao encontrado. Instale o Node.js v18+ em https://nodejs.org/
    pause
    exit /b 1
)

echo [1/3] Node.js detectado com sucesso.
echo.

echo [2/3] Verificando arquivos do projeto...
if not exist "package.json" (
    if exist "ubjcontabil\\package.json" (
        cd ubjcontabil
    ) else (
        echo Criando package.json essencial...
        (
            echo {
            echo   "name": "ubj-contabil",
            echo   "private": true,
            echo   "version": "1.0.0",
            echo   "type": "module",
            echo   "scripts": {
            echo     "dev": "vite --port=3000 --host=0.0.0.0",
            echo     "build": "vite build"
            echo   },
            echo   "dependencies": {
            echo     "@tailwindcss/vite": "^4.3.3",
            echo     "@vitejs/plugin-react": "^6.1.1",
            echo     "lucide-react": "^0.546.0",
            echo     "react": "^19.0.1",
            echo     "react-dom": "^19.0.1",
            echo     "vite": "^8.3.0",
            echo     "tailwindcss": "^4.3.3"
            echo   },
            echo   "devDependencies": {
            echo     "@types/node": "^22.14.0",
            echo     "@types/react": "^19.3.0",
            echo     "@types/react-dom": "^19.3.0",
            echo     "typescript": "^7.0.2"
            echo   }
            echo }
        ) > package.json
    )
)

if not exist ".env" (
    (
        echo PORT=3000
        echo DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ubj_contabil
        echo NODE_ENV=development
    ) > .env
)

echo.
echo [3/3] Instalando dependencias com npm...
call npm install

echo.
echo ============================================================
echo     UBJ CONTABIL - CONFIGURACAO CONCLUIDA COM SUCESSO!
echo ============================================================
echo Para iniciar o sistema agora:
echo.
echo     npm run dev
echo.
pause
call npm run dev`;

const SCRIPT_SYNC_SH = `#!/usr/bin/env bash
# ====================================================================
# UBJ CONTÁBIL - SCRIPT DE ATUALIZAÇÃO E SINCRONIZAÇÃO COM O GITHUB
# ====================================================================

set -e

echo ""
echo "============================================================"
echo "    UBJ CONTÁBIL - Sincronização com o Repositório Remoto   "
echo "============================================================"
echo ""

if [ ! -d ".git" ]; then
    echo "Inicializando repositório Git local..."
    git init
    git remote add origin "https://github.com/neimargomespvh/ubjcontabil.git" || true
fi

CURRENT_BRANCH=$(git branch --show-current || echo "main")
echo "[1/3] Branch ativa: '$CURRENT_BRANCH'"
echo ""

echo "[2/3] Preparando commit de todas as alterações..."
git add -A

read -p "Digite a mensagem do commit [ENTER para automática]: " COMMIT_MSG
if [ -z "$COMMIT_MSG" ]; then
    COMMIT_MSG="feat(contabil): atualizacao automatica em $(date '+%d/%m/%Y %H:%M:%S')"
fi

git commit -m "$COMMIT_MSG" || true

echo ""
echo "[3/3] Enviando alterações para origin/main..."
git branch -M main
git push -u origin main

echo ""
echo "============================================================"
echo "    REPOSITÓRIO UBJ CONTÁBIL ATUALIZADO COM SUCESSO!        "
echo "============================================================"`;

const SCRIPT_SYNC_BAT = `@echo off
REM ====================================================================
REM UBJ CONTÁBIL - SCRIPT DE ATUALIZAÇÃO COM O GITHUB (WINDOWS)
REM ====================================================================

echo ============================================================
echo     UBJ CONTABIL - Sincronizacao com o GitHub (Windows)
echo ============================================================
echo.

if not exist ".git" (
    git init
    git remote add origin https://github.com/neimargomespvh/ubjcontabil.git
)

echo [1/3] Preparando arquivos...
git add -A

set /p MSG=Digite a mensagem do commit (ENTER para padrao): 
if "%MSG%"=="" set MSG=feat(contabil): atualizacao automatica

git commit -m "%MSG%"

echo.
echo [2/3] Sincronizando com o GitHub...
git branch -M main
git push -u origin main

echo.
echo ============================================================
echo     PROJETO ATUALIZADO COM SUCESSO NO GITHUB!
echo ============================================================
pause`;

export const LocalDevScriptsTab: React.FC = () => {
  const [activeScript, setActiveScript] = useState<'setup-sh' | 'setup-bat' | 'sync-sh' | 'sync-bat'>('setup-sh');
  const [copied, setCopied] = useState<boolean>(false);
  const [isZipping, setIsZipping] = useState<boolean>(false);

  const getScriptContent = () => {
    switch (activeScript) {
      case 'setup-sh': return { code: SCRIPT_SETUP_SH, filename: 'setup-local.sh', os: 'Linux / macOS / WSL' };
      case 'setup-bat': return { code: SCRIPT_SETUP_BAT, filename: 'setup-local.bat', os: 'Windows (CMD)' };
      case 'sync-sh': return { code: SCRIPT_SYNC_SH, filename: 'atualizar-repositorio.sh', os: 'Linux / macOS / WSL' };
      case 'sync-bat': return { code: SCRIPT_SYNC_BAT, filename: 'atualizar-repositorio.bat', os: 'Windows (CMD)' };
    }
  };

  const current = getScriptContent();

  const handleCopy = () => {
    navigator.clipboard.writeText(current.code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const blob = new Blob([current.code], { type: 'text/plain;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = current.filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleDownloadFullZip = async () => {
    setIsZipping(true);
    try {
      const blob = await generateProjectZip();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'ubjcontabil-completo.zip';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
    } finally {
      setIsZipping(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Diagnóstico do Erro ENOENT do Usuário */}
      <div className="bg-amber-950/40 border border-amber-600/40 rounded-xl p-5 shadow-sm text-amber-100">
        <div className="flex items-start gap-3">
          <div className="p-2 bg-amber-500/20 text-amber-400 rounded-lg mt-0.5">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <h3 className="font-bold text-amber-200 text-sm">
              Diagnóstico do Erro: <code>npm ERR! code ENOENT ... ubjcontabil/package.json</code>
            </h3>
            <p className="text-xs text-amber-200/90 mt-1 leading-relaxed">
              Esse erro aconteceu porque você já estava dentro da pasta <code>~/Projetos/UbjContabil</code> e o repositório remoto no GitHub ainda não possuía o <code>package.json</code> sincronizado.
            </p>
            <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
              <div className="p-3 bg-amber-900/30 rounded-lg border border-amber-800/40">
                <span className="font-bold text-amber-200 block mb-1">Solução 1: Baixar ZIP Completo (Mais Rápido)</span>
                <p className="text-amber-200/80 mb-2">
                  Baixe o ZIP abaixo e extraia os arquivos diretamente dentro de <code>~/Projetos/UbjContabil</code>. Depois execute <code>npm install && npm run dev</code>.
                </p>
                <button
                  onClick={handleDownloadFullZip}
                  disabled={isZipping}
                  className="px-3 py-1.5 rounded-lg bg-amber-500 text-slate-950 font-bold text-xs flex items-center gap-1.5 hover:bg-amber-400 transition-colors cursor-pointer"
                >
                  <FileArchive className="w-4 h-4" />
                  {isZipping ? 'Compactando...' : 'Baixar ZIP do Projeto'}
                </button>
              </div>

              <div className="p-3 bg-amber-900/30 rounded-lg border border-amber-800/40">
                <span className="font-bold text-amber-200 block mb-1">Solução 2: Executar Script Atualizado</span>
                <p className="text-amber-200/80 mb-2">
                  O script <code>setup-local.sh</code> foi atualizado! Ele agora detecta que você já está na pasta e gera automaticamente os arquivos se estiverem ausentes.
                </p>
                <button
                  onClick={handleDownload}
                  className="px-3 py-1.5 rounded-lg bg-slate-800 text-amber-300 border border-amber-600/40 font-semibold text-xs flex items-center gap-1.5 hover:bg-slate-700 transition-colors cursor-pointer"
                >
                  <Download className="w-4 h-4" />
                  Baixar setup-local.sh Atualizado
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Header Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 sm:p-6 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-emerald-500/10 text-emerald-400 rounded-xl border border-emerald-500/20">
              <Laptop className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white tracking-tight">
                Scripts de Setup Local & Sincronização Git
              </h2>
              <p className="text-xs sm:text-sm text-slate-400 mt-0.5">
                Automatização completa para baixar, editar no seu computador (VS Code) e sincronizar alterações no GitHub.
              </p>
            </div>
          </div>

          <button
            onClick={handleDownloadFullZip}
            disabled={isZipping}
            className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs transition-colors shadow-md shadow-emerald-950/40 cursor-pointer self-start sm:self-auto"
          >
            <FileArchive className="w-4 h-4" />
            {isZipping ? 'Gerando ZIP...' : 'Baixar Projeto Completo (.zip)'}
          </button>
        </div>

        {/* 2-Step Workflows */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6 pt-5 border-t border-slate-800 text-xs">
          <div className="p-4 bg-slate-800/40 rounded-xl border border-slate-700/60">
            <div className="flex items-center gap-2 text-emerald-400 font-bold text-sm mb-1.5">
              <FolderDown className="w-4 h-4" />
              1. Script de Download & Instalação Local (Resiliente)
            </div>
            <p className="text-slate-300 leading-relaxed">
              Detecta automaticamente se você já está na pasta do projeto, cria o <code>package.json</code> caso ainda não exista no repositório, instala as dependências com <code>npm install</code> e inicia o servidor.
            </p>
            <div className="mt-3 flex gap-2">
              <button
                onClick={() => setActiveScript('setup-sh')}
                className={`px-3 py-1.5 rounded-lg font-mono font-medium transition-colors cursor-pointer ${
                  activeScript === 'setup-sh' ? 'bg-emerald-600 text-white' : 'bg-slate-900 text-slate-400 hover:text-white'
                }`}
              >
                setup-local.sh (Linux/Mac)
              </button>
              <button
                onClick={() => setActiveScript('setup-bat')}
                className={`px-3 py-1.5 rounded-lg font-mono font-medium transition-colors cursor-pointer ${
                  activeScript === 'setup-bat' ? 'bg-emerald-600 text-white' : 'bg-slate-900 text-slate-400 hover:text-white'
                }`}
              >
                setup-local.bat (Windows)
              </button>
            </div>
          </div>

          <div className="p-4 bg-slate-800/40 rounded-xl border border-slate-700/60">
            <div className="flex items-center gap-2 text-teal-400 font-bold text-sm mb-1.5">
              <UploadCloud className="w-4 h-4" />
              2. Script de Atualização Rápida no GitHub
            </div>
            <p className="text-slate-300 leading-relaxed">
              Após editar o sistema no seu computador, basta executar este script: ele inicializa o git (se necessário), faz <code>git add -A</code>, cria o commit e envia tudo com <code>git push -u origin main</code>.
            </p>
            <div className="mt-3 flex gap-2">
              <button
                onClick={() => setActiveScript('sync-sh')}
                className={`px-3 py-1.5 rounded-lg font-mono font-medium transition-colors cursor-pointer ${
                  activeScript === 'sync-sh' ? 'bg-teal-600 text-white' : 'bg-slate-900 text-slate-400 hover:text-white'
                }`}
              >
                atualizar-repositorio.sh
              </button>
              <button
                onClick={() => setActiveScript('sync-bat')}
                className={`px-3 py-1.5 rounded-lg font-mono font-medium transition-colors cursor-pointer ${
                  activeScript === 'sync-bat' ? 'bg-teal-600 text-white' : 'bg-slate-900 text-slate-400 hover:text-white'
                }`}
              >
                atualizar-repositorio.bat (Windows)
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Script Code Viewer & Actions */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-lg">
        <div className="bg-slate-800/80 px-4 py-3 border-b border-slate-800 flex items-center justify-between text-xs font-mono text-slate-300">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-emerald-400" />
            <span className="font-bold text-white">{current.filename}</span>
            <span className="text-slate-500">({current.os})</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-white text-xs font-medium transition-colors cursor-pointer"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? 'Copiado!' : 'Copiar Script'}
            </button>

            <button
              onClick={handleDownload}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium transition-colors cursor-pointer"
            >
              <Download className="w-3.5 h-3.5" />
              Baixar {current.filename}
            </button>
          </div>
        </div>

        <pre className="p-4 sm:p-6 text-xs font-mono text-emerald-300/90 overflow-x-auto leading-relaxed bg-slate-950 max-h-[500px]">
          <code>{current.code}</code>
        </pre>
      </div>

      {/* 2-Step Terminal Commands */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 sm:p-6 space-y-4">
        <h3 className="font-bold text-slate-100 text-sm flex items-center gap-2">
          <Terminal className="w-4 h-4 text-emerald-400" />
          Comando Rápido para Rodar no seu Terminal Agora
        </h3>
        <p className="text-xs text-slate-400">
          Como você já está na pasta <code>~/Projetos/UbjContabil</code>, você pode colar os comandos abaixo para inicializar e rodar o projeto imediatamente:
        </p>

        <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl font-mono text-xs text-slate-200 space-y-2 overflow-x-auto">
          <div className="text-slate-500"># 1. Se existir a subpasta vazia ubjcontabil criada anteriormente, remova-a:</div>
          <div className="text-emerald-400">rm -rf ubjcontabil</div>
          <div className="text-slate-500 mt-2"># 2. Baixe o script atualizado e execute:</div>
          <div className="text-emerald-400">./setup-local.sh</div>
          <div className="text-slate-500 mt-2"># 3. O script criará o package.json, rodará o npm install e iniciará o sistema em http://localhost:3000!</div>
        </div>
      </div>
    </div>
  );
};
