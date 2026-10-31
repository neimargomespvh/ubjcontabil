"""Extrator de participantes (clientes/fornecedores) da Fortes."""
from __future__ import annotations

import threading
from collections.abc import Iterator
from typing import Any

from src.domain.contracts.extractor import IEntityExtractor
from src.domain.models.chunk import Chunk
from src.domain.models.entities.participante import ParticipanteOrigem
from src.extract.fortes.connection import FortesConnectionFactory
from src.extract.shared.sqlserver_chunk_reader import SqlServerChunkReader


class FortesParticipanteExtractor(IEntityExtractor[ParticipanteOrigem]):
    """Extrai PARTICIPANTE com WITH (NOLOCK) + keyset pagination."""

    _SQL = """
        SELECT  P.CODIGO, P.RAZAO_SOCIAL, P.NOME_FANTASIA, P.CNPJ_CPF,
                P.IE, P.IM, P.ENDERECO, P.CIDADE, P.UF, P.CEP,
                P.EMAIL, P.TELEFONE, P.TIPO_PESSOA
        FROM    dbo.PARTICIPANTE P WITH (NOLOCK)
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
                    "SELECT COUNT_BIG(*) FROM dbo.PARTICIPANTE WITH (NOLOCK)"
                )
                row = cur.fetchone()
                return int(str(row[0])) if row and row[0] is not None else None
        except Exception:
            return None

    def extract(
        self, stop_event: threading.Event | None = None
    ) -> Iterator[Chunk[ParticipanteOrigem]]:
        total = 0
        with self._factory.open() as conn:
            for lote in self._reader.ler(
                conn, self._SQL, "CODIGO", self._mapear, stop_event
            ):
                total += len(lote)
                yield Chunk(itens=lote, total_acumulado=total)

    @staticmethod
    def _mapear(r: Any) -> ParticipanteOrigem:
        return ParticipanteOrigem(
            codigo_origem=int(r["CODIGO"]),
            razao_social=r.get("RAZAO_SOCIAL"),
            nome_fantasia=r.get("NOME_FANTASIA"),
            documento=r.get("CNPJ_CPF"),
            inscricao_estadual=r.get("IE"),
            inscricao_municipal=r.get("IM"),
            endereco=r.get("ENDERECO"),
            cidade=r.get("CIDADE"),
            uf=r.get("UF"),
            cep=r.get("CEP"),
            email=r.get("EMAIL"),
            telefone=r.get("TELEFONE"),
            tipo_pessoa=r.get("TIPO_PESSOA"),
        )
