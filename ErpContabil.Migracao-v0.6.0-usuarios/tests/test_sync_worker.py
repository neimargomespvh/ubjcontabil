"""Testes do SyncWorker (usa mock do DeltaClient, sem tocar nuvem)."""
from __future__ import annotations

import os
import uuid
from typing import Any

import pytest

psycopg = pytest.importorskip("psycopg")

pytestmark = pytest.mark.integration


def _conninfo() -> str:
    return os.environ.get("ERP_TEST_DATABASE_URL", "")


@pytest.fixture(scope="module")
def db_ok() -> bool:
    if not _conninfo():
        pytest.skip("ERP_TEST_DATABASE_URL não setado")
    try:
        with psycopg.connect(_conninfo(), connect_timeout=2):
            return True
    except Exception:
        pytest.skip("PostgreSQL não disponível")


class _MockClient:
    def __init__(self, resposta: bool = True) -> None:
        self._resposta = resposta
        self.payloads: list[dict[str, Any]] = []

    def enviar(self, lote: dict[str, Any]) -> bool:
        self.payloads.append(lote)
        return self._resposta


def _inserir_evento(conn: psycopg.Connection, empresa: str, entidade: str,
                    registro_id: str, operacao: str = "UPSERT") -> str:
    rid = str(uuid.uuid4())
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO sync.sync_outbox "
            "(id, empresa_id, entidade, operacao, registro_id) "
            "VALUES (%s, %s, %s, %s, %s)",
            (rid, empresa, entidade, operacao, registro_id),
        )
    return rid


def test_worker_processa_upsert(db_ok: bool) -> None:
    from src.infrastructure.sync.sync_worker import SyncWorker

    if not db_ok:
        return
    empresa = f"test-{uuid.uuid4().hex[:8]}"
    with psycopg.connect(_conninfo()) as conn:
        # cria um participante real
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO erp.participante "
                "(empresa_id, codigo_origem, origem_sistema, razao_social, "
                " documento, tipo_pessoa) "
                "VALUES (%s, 1, 'TEST', 'Foo', '11222333000181', 'JURIDICA')",
                (empresa,),
            )
        ev_id = _inserir_evento(conn, empresa, "participante", "1")
        conn.commit()

        mock = _MockClient(resposta=True)
        worker = SyncWorker(_conninfo(), "http://mock", "key", client=mock)
        n = worker.processar_um_lote()

        assert n >= 1
        assert any(
            any(e.get("registro_id") == "1" and e.get("operacao") == "UPSERT"
                for e in p["eventos"])
            for p in mock.payloads
        )

        with conn.cursor() as cur:
            cur.execute(
                "SELECT sincronizado_em FROM sync.sync_outbox WHERE id = %s",
                (ev_id,),
            )
            row = cur.fetchone()
            assert row is not None and row[0] is not None

        conn.execute("DELETE FROM erp.participante WHERE empresa_id = %s", (empresa,))
        conn.commit()


def test_worker_falha_incrementa_tentativas(db_ok: bool) -> None:
    from src.infrastructure.sync.sync_worker import SyncWorker

    if not db_ok:
        return
    empresa = f"test-{uuid.uuid4().hex[:8]}"
    with psycopg.connect(_conninfo()) as conn:
        ev_id = _inserir_evento(conn, empresa, "participante", "999")
        conn.commit()

        mock = _MockClient(resposta=False)
        worker = SyncWorker(_conninfo(), "http://mock", "key", client=mock)
        worker.processar_um_lote()

        with conn.cursor() as cur:
            cur.execute(
                "SELECT tentativas, sincronizado_em FROM sync.sync_outbox WHERE id = %s",
                (ev_id,),
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] >= 1
            assert row[1] is None

        conn.execute("DELETE FROM sync.sync_outbox WHERE id = %s", (ev_id,))
        conn.commit()
