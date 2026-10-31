#!/usr/bin/env python3
"""Sobe o SyncWorker (processo separado do painel)."""
from __future__ import annotations

import logging
import os
import signal
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.infrastructure.sync.sync_worker import SyncWorker

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("sync-worker")


def main() -> int:
    conninfo = os.environ.get(
        "ERP_DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/erp_contabil",
    )
    # Compat: DELTA_* ou CLOUD_SYNC_*
    base_url = os.environ.get("DELTA_BASE_URL") or os.environ.get("CLOUD_SYNC_URL", "")
    api_key = os.environ.get("DELTA_API_KEY") or os.environ.get("CLOUD_SYNC_API_KEY", "")
    batch = int(os.environ.get("SYNC_BATCH_SIZE", "100"))
    poll = float(os.environ.get("SYNC_POLL_INTERVAL_S", "5"))

    if not base_url:
        log.warning(
            "DELTA_BASE_URL / CLOUD_SYNC_URL não configurado — "
            "worker processará outbox localmente (sem envio remoto)"
        )

    worker = SyncWorker(
        conninfo,
        base_url or "http://localhost:0",  # placeholder; client deve tolerar
        api_key or "",
        batch_size=batch,
        poll_interval_s=poll,
    )
    worker.start()

    def _stop(signum: int, _frame: object) -> None:
        log.info("Sinal %s — encerrando…", signum)
        worker.stop()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    log.info("SyncWorker rodando (batch=%s poll=%.1fs)", batch, poll)
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    raise SystemExit(main())
