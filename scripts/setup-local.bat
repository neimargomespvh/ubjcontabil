@echo off
REM ====================================================================
REM UBJ CONTÁBIL - SCRIPT RESILIENTE DE SETUP LOCAL (WINDOWS)
REM ====================================================================

echo ============================================================
echo     UBJ CONTABIL - Configuracao do Ambiente Local (Windows)
echo ============================================================
echo.

set REPO_URL=https://github.com/neimargomespvh/ubjcontabil.git

REM 1. Verificar Git e Node
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo ERRO: Node.js nao encontrado. Instale o Node.js v18+ em https://nodejs.org/
    pause
    exit /b 1
)

echo [1/3] Node.js detectado com sucesso.
echo.

REM 2. Verificar package.json
echo [2/3] Verificando arquivos do projeto...
if not exist "package.json" (
    if exist "ubjcontabil\package.json" (
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
            echo     "build": "vite build",
            echo     "preview": "vite preview"
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
REM 3. Instalar dependencias
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
call npm run dev
