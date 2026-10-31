#!/usr/bin/env python3
"""Demo: executa a migração Fortes sem o painel web (CLI)."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import argparse
import os

from src.domain.models.migration_options import FortesConnectionOptions
from src.infrastructure.logging.migration_logger import MigrationLogger
from src.infrastructure.orchestrator import MigrationOrchestrator
from src.load.postgres_bulk_loader import PostgresBinaryBulkLoader
from src.load.postgres_fallback_loader import PostgresFallbackRowLoader
from src.load.sync_outbox_writer import SyncOutboxWriter
from src.transform.participante_transformer import ParticipanteTransformer


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", required=True)
    p.add_argument("--porta", type=int, default=1433)
    p.add_argument("--database", required=True)
    p.add_argument("--usuario", required=True)
    p.add_argument("--senha", required=True)
    p.add_argument("--empresa-id", required=True)
    p.add_argument("--etapas", default="empresa,plano_contas,participante")
    p.add_argument("--conninfo", default=os.environ.get(
        "ERP_DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/erp_contabil"))
    args = p.parse_args()

    opt = FortesConnectionOptions(
        host=args.host, porta=args.porta, database=args.database,
        usuario=args.usuario, senha=args.senha, empresa_id=args.empresa_id,
    )
    logger = MigrationLogger(Path("migracao_erros.log"), args.conninfo)
    orc = MigrationOrchestrator(
        conninfo=args.conninfo, logger=logger,
        bulk_loader=PostgresBinaryBulkLoader(args.conninfo),
        fallback_loader=PostgresFallbackRowLoader(logger),
        outbox=SyncOutboxWriter(),
        transformer=ParticipanteTransformer(),
    )

    print(f"🔌 Testando {args.host}:{args.porta}/{args.database}…")
    if not orc.testar_conexao_fortes(opt):
        print("❌ Falha na conexão. Ver migracao_erros.log.", file=sys.stderr)
        return 1
    print("✅ Conexão OK\n")

    etapas = tuple(e.strip() for e in args.etapas.split(","))

    def _cb(p: object) -> None:
        prog = getattr(p, "percentual", 0.0)
        etapa = getattr(p, "etapa_atual", "")
        print(f"  [{prog:5.1f}%] {etapa}")

    print(f"🚀 Migrando etapas: {etapas}\n")
    result = orc.executar_migracao_fortes(opt, _cb, etapas=etapas)
    print(f"\n{'✅' if result.sucesso else '❌'} "
          f"Importados: {result.importados} · Erros: {result.erros} · "
          f"Duração: {result.duracao_segundos:.1f}s")
    return 0 if result.sucesso else 1


if __name__ == "__main__":
    sys.exit(main())
