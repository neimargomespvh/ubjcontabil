"""Extrator do cadastro de empresas da Fortes."""
from __future__ import annotations

import threading
from collections.abc import Iterator
from typing import Any

from src.domain.contracts.extractor import IEntityExtractor
from src.domain.models.chunk import Chunk
from src.domain.models.entities.empresa import EmpresaOrigem
from src.extract.fortes.connection import FortesConnectionFactory
from src.extract.shared.sqlserver_chunk_reader import SqlServerChunkReader


class FortesEmpresaExtractor(IEntityExtractor[EmpresaOrigem]):
    """Extrai EMPRESA com WITH (NOLOCK) + keyset pagination."""

    _SQL = """
        SELECT  E.CODIGO, E.RAZAO_SOCIAL, E.CNPJ, E.UF, E.REGIME_TRIBUTARIO
        FROM    dbo.EMPRESA E WITH (NOLOCK)
        WHERE   E.CODIGO > %s
        ORDER BY E.CODIGO
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
                cur.execute("SELECT COUNT_BIG(*) FROM dbo.EMPRESA WITH (NOLOCK)")
                row = cur.fetchone()
                return int(str(row[0])) if row and row[0] is not None else None
        except Exception:
            return None

    def extract(
        self, stop_event: threading.Event | None = None
    ) -> Iterator[Chunk[EmpresaOrigem]]:
        total = 0
        with self._factory.open() as conn:
            for lote in self._reader.ler(
                conn, self._SQL, "CODIGO", self._mapear, stop_event
            ):
                total += len(lote)
                yield Chunk(itens=lote, total_acumulado=total)

    @staticmethod
    def _mapear(r: Any) -> EmpresaOrigem:
        return EmpresaOrigem(
            codigo_origem=int(r["CODIGO"]),
            razao_social=r.get("RAZAO_SOCIAL"),
            cnpj=r.get("CNPJ"),
            uf=r.get("UF"),
            regime_tributario=r.get("REGIME_TRIBUTARIO"),
        )
