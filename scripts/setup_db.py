#!/usr/bin/env python3
"""setup_db.py — Cria o banco `erp_contabil` e aplica `ddl/init.sql`.

Não precisa de `psql` instalado — usa o próprio psycopg.

Uso:
    # Verifica a conexão e mostra o que faria:
    python scripts/setup_db.py --dry-run

    # Aplica:
    python scripts/setup_db.py

    # Customizar credenciais:
    DATABASE_URL="postgresql://user:senha@host:5432/postgres" \\
        python scripts/setup_db.py

Pré-requisitos:
    - PostgreSQL rodando em localhost:5432 (nativo ou Docker)
    - Usuário com permissão para CREATE DATABASE
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg

DEFAULT_ADMIN_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres"
)
APP_DB = os.environ.get("APP_DB", "erp_contabil")


def _admin_url_without_db(url: str) -> str:
    """Troca o path final por /postgres (banco administrativo)."""
    base, _, _ = url.rpartition("/")
    return f"{base}/postgres"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--db", default=APP_DB, help="Nome do banco a criar")
    parser.add_argument(
        "--ddl", default="ddl/init.sql", help="Caminho do DDL a aplicar"
    )
    args = parser.parse_args()

    ddl_path = Path(args.ddl)
    if not ddl_path.exists():
        print(f"❌ DDL não encontrado: {ddl_path}", file=sys.stderr)
        return 1

    admin_url = _admin_url_without_db(DEFAULT_ADMIN_URL)
    app_url = DEFAULT_ADMIN_URL.rpartition("/")[0] + f"/{args.db}"

    print(f"🔌 Admin:  {admin_url}")
    print(f"🔌 App:    {app_url}")
    print(f"🗄️  DDL:    {ddl_path}")

    if args.dry_run:
        print("\n(dry-run — nada foi executado)")
        return 0

    # 1. Garante que o banco existe
    try:
        with psycopg.connect(admin_url, autocommit=True) as conn:
            existe = conn.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (args.db,)
            ).fetchone()
            if not existe:
                conn.execute(f'CREATE DATABASE "{args.db}"')
                print(f"✅ Banco '{args.db}' criado")
            else:
                print(f"⏭  Banco '{args.db}' já existe")
    except psycopg.OperationalError as e:
        print(f"\n❌ Erro de conexão: {e}", file=sys.stderr)
        print("\nInstale e inicie o PostgreSQL:", file=sys.stderr)
        print("  sudo apt install postgresql postgresql-contrib", file=sys.stderr)
        print("  sudo systemctl start postgresql", file=sys.stderr)
        print("  sudo -u postgres psql -c \"ALTER USER postgres PASSWORD 'postgres';\"",
              file=sys.stderr)
        print("\nOu use Docker:", file=sys.stderr)
        print("  docker run -d --name erp-pg -e POSTGRES_PASSWORD=postgres \\",
              file=sys.stderr)
        print("      -p 5432:5432 postgres:16", file=sys.stderr)
        return 1

    # 2. Aplica o DDL
    try:
        with psycopg.connect(app_url) as conn, conn.cursor() as cur:
            cur.execute(ddl_path.read_text(encoding="utf-8"))
            conn.commit()
        print(f"✅ DDL aplicado em '{args.db}'")
    except psycopg.Error as e:
        print(f"❌ Erro ao aplicar DDL: {e}", file=sys.stderr)
        return 1

    print("\n✓ Pronto. Connection string do app:")
    print(f"  {app_url.replace(':postgres@', ':***@')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
