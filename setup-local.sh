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
echo "============================================================"