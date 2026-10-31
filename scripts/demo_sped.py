#!/usr/bin/env python3
"""Demo: importa um arquivo .txt do SPED (auditoria)."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import argparse
import os

from src.infrastructure.logging.migration_logger import MigrationLogger
from src.infrastructure.orchestrator import MigrationOrchestrator
from src.load.postgres_bulk_loader import PostgresBinaryBulkLoader
from src.load.postgres_fallback_loader import PostgresFallbackRowLoader
from src.load.sync_outbox_writer import SyncOutboxWriter
from src.transform.participante_transformer import ParticipanteTransformer


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("arquivos", nargs="+", help="Arquivos .txt do SPED")
    p.add_argument("--empresa-id", required=True)
    p.add_argument("--conninfo", default=os.environ.get(
        "ERP_DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/erp_contabil"))
    args = p.parse_args()

    for arq in args.arquivos:
        if not Path(arq).exists():
            print(f"❌ Arquivo não encontrado: {arq}", file=sys.stderr)
            return 1

    logger = MigrationLogger(Path("migracao_erros.log"), args.conninfo)
    orc = MigrationOrchestrator(
        conninfo=args.conninfo, logger=logger,
        bulk_loader=PostgresBinaryBulkLoader(args.conninfo),
        fallback_loader=PostgresFallbackRowLoader(logger),
        outbox=SyncOutboxWriter(),
        transformer=ParticipanteTransformer(),
    )

    def _cb(p: object) -> None:
        prog = getattr(p, "percentual", 0.0)
        etapa = getattr(p, "etapa_atual", "")
        print(f"  [{prog:5.1f}%] {etapa}")

    print(f"🚀 Processando {len(args.arquivos)} arquivo(s)…\n")
    result = orc.executar_migracao_arquivos(args.arquivos, args.empresa_id, _cb)
    print(f"\n{'✅' if result.sucesso else '❌'} "
          f"Importados: {result.importados} · Erros: {result.erros}")
    return 0 if result.sucesso else 1


if __name__ == "__main__":
    sys.exit(main())
