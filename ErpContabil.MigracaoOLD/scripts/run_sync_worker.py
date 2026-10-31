#!/usr/bin/env python3
"""Sobe o SyncWorker (processo separado do painel)."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import os
import signal
import time

from src.infrastructure.sync.sync_worker import SyncWorker


def main() -> int:
    conninfo = os.environ.get(
        "ERP_DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/erp_contabil",
    )
    cloud_url = os.environ.get("CLOUD_SYNC_URL", "")
    api_key = os.environ.get("CLOUD_SYNC_API_KEY", "")
    if not cloud_url or not api_key:
        print("❌ Configure CLOUD_SYNC_URL e CLOUD_SYNC_API_KEY", file=sys.stderr)
        return 1

    worker = SyncWorker(conninfo, cloud_url, api_key)
    worker.start()

    def _stop(signum: int, frame: object) -> None:
        print(f"\n⏹  Sinal {signum} — encerrando…")
        worker.stop()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    print("✓ SyncWorker rodando (Ctrl+C para parar)")
    while True:
        time.sleep(60)


if __name__ == "__main__":
    sys.exit(main())
