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

# 1. Verificar se está dentro de um repositório git
if [ ! -d ".git" ]; then
    echo "ERRO: O diretório atual não é um repositório Git."
    echo "Execute este script dentro da pasta raiz do seu projeto (ubjcontabil)."
    exit 1
fi

CURRENT_BRANCH=$(git branch --show-current || echo "main")
echo "[1/4] Branch ativa identificada: '$CURRENT_BRANCH'"
echo ""

# 2. Exibir status de modificações locais
echo "[2/4] Verificando alterações locais pendentes..."
git status --short

echo ""
read -p "Deseja salvar e enviar todas as alterações pendentes? [S/n]: " CONFIRM
if [[ "$CONFIRM" =~ ^[Nn]$ ]]; then
    echo "Operação cancelada pelo usuário."
    exit 0
fi

# 3. Adicionar e Criar Commit
echo ""
echo "[3/4] Preparando commit..."
git add -A

read -p "Digite a mensagem do commit [Pressione ENTER para mensagem automática]: " COMMIT_MSG
if [ -z "$COMMIT_MSG" ]; then
    COMMIT_MSG="feat(contabil): atualizacao automatica em $(date '+%d/%m/%Y %H:%M:%S')"
fi

# Apenas commitar se houver alterações
if git diff-index --quiet HEAD --; then
    echo "      Nenhuma alteração detectada para commit."
else
    git commit -m "$COMMIT_MSG"
    echo "      Commit criado com sucesso: '$COMMIT_MSG'"
fi

# 4. Sincronizar com o GitHub (Pull com rebase + Push)
echo ""
echo "[4/4] Sincronizando com o GitHub (pull --rebase e push)..."

echo "      Baixando atualizações remotas..."
git pull --rebase origin "$CURRENT_BRANCH" || {
    echo ""
    echo "AVISO: Houve divergência ao mesclar as alterações remotas."
    echo "Resolva os eventuais conflitos e execute 'git rebase --continue' e 'git push'."
    exit 1
}

echo "      Enviando alterações para origin/$CURRENT_BRANCH..."
git push origin "$CURRENT_BRANCH"

echo ""
echo "============================================================"
echo "    REPOSITÓRIO UBJ CONTÁBIL ATUALIZADO COM SUCESSO!        "
echo "============================================================"
echo "Todas as alterações locais foram sincronizadas no GitHub."
echo "Branch: $CURRENT_BRANCH"
echo "============================================================"
