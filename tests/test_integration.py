"""Testes de integração — exigem PostgreSQL real.

Skip automático se `ERP_TEST_DATABASE_URL` não estiver setado ou se a
conexão falhar. Rodar com:
    ERP_TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/erp_contabil_test" \\
        pytest -m integration -v
"""
from __future__ import annotations

import os
import uuid

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


def test_bulk_loader_participantes(db_ok: bool) -> None:
    from src.domain.models.entities.participante import ParticipanteDestino
    from src.load.postgres_bulk_loader import PostgresBinaryBulkLoader

    if not db_ok:
        return
    empresa_id = f"test-{uuid.uuid4().hex[:8]}"
    itens = [
        ParticipanteDestino(
            codigo_origem=i, razao_social=f"Empresa {i}",
            nome_fantasia=None, documento="11222333000181",
            tipo_pessoa="JURIDICA", inscricao_estadual=None,
            municipio="Fortaleza", uf="CE", cep=None,
            email=None, telefone=None, origem_sistema="FORTES",
        )
        for i in range(1, 4)
    ]
    loader = PostgresBinaryBulkLoader(_conninfo())
    with psycopg.connect(_conninfo()) as conn:
        with conn.transaction():
            n = loader.inserir_participantes(conn, None, empresa_id, itens)
        assert n == 3
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM erp.participante WHERE empresa_id = %s",
                (empresa_id,),
            )
            total = cur.fetchone()
            assert total is not None and total[0] == 3
        conn.execute("DELETE FROM erp.participante WHERE empresa_id = %s", (empresa_id,))
        conn.commit()
