@echo off
REM ====================================================================
REM UBJ CONTÁBIL - SCRIPT DE ATUALIZAÇÃO COM O GITHUB (WINDOWS)
REM ====================================================================

echo ============================================================
echo     UBJ CONTABIL - Sincronizacao com o GitHub (Windows)
echo ============================================================
echo.

if not exist ".git" (
    echo ERRO: O diretorio atual nao eh um repositorio Git.
    echo Execute este arquivo dentro da pasta do projeto ubjcontabil.
    pause
    exit /b 1
)

echo [1/3] Verificando modificacoes pendentes...
git status -s
echo.

set /p MSG=Digite a mensagem do commit (ENTER para padrao): 
if "%MSG%"=="" set MSG=chore: atualizacao automatica do projeto

git add -A
git commit -m "%MSG%"

echo.
echo [2/3] Baixando alteracoes remotas (git pull --rebase)...
git pull --rebase origin main

echo.
echo [3/3] Enviando alteracoes para o GitHub (git push)...
git push origin main

echo.
echo ============================================================
echo     PROJETO ATUALIZADO COM SUCESSO NO GITHUB!
echo ============================================================
pause
