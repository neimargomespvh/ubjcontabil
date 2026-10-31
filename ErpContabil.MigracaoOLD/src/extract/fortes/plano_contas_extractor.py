"""Extrator do plano de contas contábil da Fortes."""
from __future__ import annotations

import threading
from collections.abc import Iterator
from typing import Any

from src.domain.contracts.extractor import IEntityExtractor
from src.domain.models.chunk import Chunk
from src.domain.models.entities.conta_contabil import ContaContabil
from src.extract.fortes.connection import FortesConnectionFactory
from src.extract.shared.sqlserver_chunk_reader import SqlServerChunkReader


class FortesPlanoContasExtractor(IEntityExtractor[ContaContabil]):
    """Extrai PLANO_CONTAS (sintéticas + analíticas) da Fortes."""

    _SQL = """
        SELECT  P.CODIGO, P.NOME, P.CODIGO_PAI, P.NATUREZA, P.GRAU, P.NATUREZA_SALDO
        FROM    dbo.PLANO_CONTAS P WITH (NOLOCK)
        WHERE   P.CODIGO > %s
        ORDER BY P.CODIGO
        OFFSET 0 ROWS FETCH NEXT %s ROWS ONLY
    """

    def __init__(
        self, factory: FortesConnectionFactory, tamanho_chunk: int = 5_000
    ) -> None:
        self._factory = factory
        self._reader = SqlServerChunkReader(tamanho_chunk)

    def count_estimado(self) -> int | None:
        try:
            with (
                self._factory.open() as conn,
                conn.cursor() as cur,
            ):
                cur.execute(
                    "SELECT COUNT_BIG(*) FROM dbo.PLANO_CONTAS WITH (NOLOCK)"
                )
                row = cur.fetchone()
                return int(str(row[0])) if row and row[0] is not None else None
        except Exception:
            return None

    def extract(
        self, stop_event: threading.Event | None = None
    ) -> Iterator[Chunk[ContaContabil]]:
        total = 0
        with self._factory.open() as conn:
            for lote in self._reader.ler(
                conn, self._SQL, "CODIGO", self._mapear, stop_event
            ):
                total += len(lote)
                yield Chunk(itens=lote, total_acumulado=total)

    @staticmethod
    def _mapear(r: Any) -> ContaContabil:
        natureza = (r.get("NATUREZA") or "ANALITICA").upper()
        if natureza not in ("SINTETICA", "ANALITICA"):
            natureza = "SINTETICA" if natureza in ("S", "01", "1") else "ANALITICA"
        return ContaContabil(
            codigo=str(r["CODIGO"]),
            nome=r.get("NOME") or "(sem nome)",
            codigo_pai=r.get("CODIGO_PAI"),
            natureza=natureza,
            grau=int(r.get("GRAU") or 1),
            natureza_saldo=r.get("NATUREZA_SALDO"),
        )
