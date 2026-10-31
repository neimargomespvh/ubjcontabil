"""Worker que drena a outbox local e envia deltas para a nuvem."""
from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass
from typing import Any, cast

import psycopg
from psycopg.rows import dict_row

from src.infrastructure.sync.delta_client import DeltaClient

log = logging.getLogger(__name__)


_TABELAS: dict[str, tuple[str, str]] = {
    "participante":   ("erp.participante",    "codigo_origem"),
    "empresa":        ("erp.empresa",         "codigo_origem"),
    "conta_contabil": ("erp.conta_contabil",  "codigo"),
}

_LOTE_MAX_TENTATIVAS = 5
_BACKOFF_BASE_S = 30.0
_BACKOFF_MAX_S = 900.0


@dataclass(slots=True)
class _EventoOutbox:
    id: str
    empresa_id: str
    entidade: str
    operacao: str
    registro_id: str
    tentativas: int


class SyncWorker:
    """Drena `sync.sync_outbox` em lotes e envia para a nuvem."""

    def __init__(
        self,
        conninfo: str,
        base_url: str,
        api_key: str,
        batch_size: int = 100,
        poll_interval_s: float = 5.0,
        client: DeltaClient | None = None,
    ) -> None:
        self._conninfo = conninfo
        self._batch_size = batch_size
        self._poll = poll_interval_s
        self._client = client or DeltaClient(base_url, api_key)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # -- lifecycle ----------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="SyncWorker")
        self._thread.start()

    def stop(self, timeout_s: float = 10.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout_s)

    def _run(self) -> None:
        log.info("SyncWorker iniciado (intervalo %.1fs)", self._poll)
        while not self._stop.is_set():
            try:
                n = self.processar_um_lote()
                if n == 0:
                    self._stop.wait(self._poll)
                else:
                    log.info("Lote sincronizado: %d eventos", n)
            except Exception:
                log.exception("Erro no SyncWorker")
                self._stop.wait(self._poll * 2)

    # -- processamento -----------------------------------------------
    def processar_um_lote(self) -> int:
        """Processa até `batch_size` eventos pendentes. Retorna quantos OK."""
        with (
            psycopg.connect(self._conninfo, row_factory=dict_row) as conn,
            conn.transaction(),
        ):
            eventos = self._pegar_lote(conn)
            if not eventos:
                return 0

            por_empresa: dict[str, list[_EventoOutbox]] = {}
            for ev in eventos:
                por_empresa.setdefault(ev.empresa_id, []).append(ev)

            total_ok = 0
            for empresa_id, evs in por_empresa.items():
                ok, falhas = self._enviar_empresa(conn, empresa_id, evs)
                total_ok += ok
                self._marcar(conn, evs, falhas)
            return total_ok

    def _pegar_lote(
        self, conn: psycopg.Connection[dict[str, Any]]
    ) -> list[_EventoOutbox]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, empresa_id, entidade, operacao, registro_id, tentativas
                FROM sync.sync_outbox
                WHERE sincronizado_em IS NULL
                  AND agendado_para <= now()
                  AND tentativas < %s
                ORDER BY criado_em
                LIMIT %s
                FOR UPDATE SKIP LOCKED
                """,
                (_LOTE_MAX_TENTATIVAS, self._batch_size),
            )
            rows = cast(list[dict[str, Any]], cur.fetchall())
        return [
            _EventoOutbox(
                id=str(r["id"]), empresa_id=str(r["empresa_id"]),
                entidade=str(r["entidade"]), operacao=str(r["operacao"]),
                registro_id=str(r["registro_id"]),
                tentativas=int(r["tentativas"]),
            )
            for r in rows
        ]

    def _enviar_empresa(
        self, conn: psycopg.Connection[dict[str, Any]], empresa_id: str,
        eventos: list[_EventoOutbox],
    ) -> tuple[int, dict[str, str]]:
        payload_eventos: list[dict[str, Any]] = []
        for ev in eventos:
            if ev.operacao == "DELETE":
                payload_eventos.append({
                    "entidade": ev.entidade, "operacao": "DELETE",
                    "registro_id": ev.registro_id,
                })
                continue
            dados = self._buscar_dados(conn, ev)
            if dados is None:
                payload_eventos.append({
                    "entidade": ev.entidade, "operacao": "DELETE",
                    "registro_id": ev.registro_id,
                })
            else:
                payload_eventos.append({
                    "entidade": ev.entidade, "operacao": "UPSERT",
                    "registro_id": ev.registro_id, "dados": dados,
                })

        lote = {
            "lote_id": str(uuid.uuid4()),
            "empresa_id": empresa_id,
            "eventos": payload_eventos,
        }
        if self._client.enviar(lote):
            return len(eventos), {}
        return 0, {ev.id: "envio falhou" for ev in eventos}

    def _buscar_dados(
        self, conn: psycopg.Connection[dict[str, Any]], ev: _EventoOutbox,
    ) -> dict[str, Any] | None:
        tabela, coluna_chave = _TABELAS.get(ev.entidade, (None, None))
        if tabela is None:
            return None
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM {tabela} WHERE empresa_id = %s AND {coluna_chave} = %s",
                (ev.empresa_id, ev.registro_id),
            )
            row = cast(dict[str, Any] | None, cur.fetchone())
            return row

    def _marcar(
        self, conn: psycopg.Connection[dict[str, Any]], evs: list[_EventoOutbox],
        falhas: dict[str, str],
    ) -> None:
        with conn.cursor() as cur:
            for ev in evs:
                if ev.id not in falhas:
                    cur.execute(
                        "UPDATE sync.sync_outbox SET sincronizado_em = now() "
                        "WHERE id = %s",
                        (ev.id,),
                    )
                    continue

                novas = ev.tentativas + 1
                if novas >= _LOTE_MAX_TENTATIVAS:
                    cur.execute(
                        "INSERT INTO sync.sync_dlq "
                        "(id, empresa_id, entidade, operacao, registro_id, tentativas, erro) "
                        "SELECT id, empresa_id, entidade, operacao, registro_id, %s, %s "
                        "FROM sync.sync_outbox WHERE id = %s",
                        (novas, falhas[ev.id], ev.id),
                    )
                    cur.execute("DELETE FROM sync.sync_outbox WHERE id = %s", (ev.id,))
                else:
                    backoff = min(_BACKOFF_MAX_S, _BACKOFF_BASE_S * (2 ** novas))
                    cur.execute(
                        "UPDATE sync.sync_outbox SET tentativas = %s, "
                        "agendado_para = now() + (%s || ' seconds')::interval "
                        "WHERE id = %s",
                        (novas, str(int(backoff)), ev.id),
                    )
