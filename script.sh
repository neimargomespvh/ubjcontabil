#!/usr/bin/env bash
# setup-python.sh — Bootstrap do ambiente Python (venv)
set -euo pipefail
ROOT="ErpContabil.Migracao"

command -v python3 >/dev/null || { echo "Instale Python 3.11+"; exit 1; }
python3 -c 'import sys; assert sys.version_info >= (3,11), sys.version' \
  || { echo "Python 3.11+ necessário"; exit 1; }
echo "✓ $(python3 --version)"

mkdir -p "$ROOT"/{src/{domain/{contracts,models,enums},extract/{fortes,tron,shared},transform/{mappings,validators,sped,normalizers},load,infrastructure/{logging,resilience,telemetry},web/{templates,static}},tests,data}

cat > "$ROOT/requirements.txt" <<'EOF'
pymssql>=2.3.0
firebird-driver>=2.0.0
psycopg[binary]>=3.2.0
python-dotenv>=1.0.0
pydantic>=2.9.0
pydantic-settings>=2.5.0
rich>=13.9.0
tqdm>=4.66.0
ruff>=0.7.0
mypy>=1.11.0
pytest>=8.3.0
pytest-asyncio>=0.24.0
EOF

rm -rf "$ROOT/.venv"
python3 -m venv "$ROOT/.venv"
# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"

python -m pip install --upgrade pip wheel setuptools >/dev/null
pip install -r "$ROOT/requirements.txt"

pip check
python -c "
import importlib
for m in ['psycopg','pymssql','firebird.driver','pydantic','rich','tqdm','dotenv']:
    importlib.import_module(m)
print('✓ todas as dependências OK')
"

echo
echo "✓ Ambiente Python pronto!"
echo "  Ativar:  source $ROOT/.venv/bin/activate"
echo "  Rodar:   python -m src.web.app"