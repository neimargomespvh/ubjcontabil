#!/usr/bin/env bash
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
echo "============================================================"