"""Paginação por keyset para SQL Server (chunks de N registros)."""
from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from typing import Any

import pymssql


class SqlServerChunkReader:
    """Lê tabelas grandes em lotes com keyset pagination.

    O `sql_template` DEVE conter dois placeholders `%s`:
      - 1º: último valor da chave (inicia em 0)
      - 2º: tamanho do lote (LIMIT / FETCH NEXT)

    Exemplo:
        SELECT CODIGO, NOME FROM TABELA WITH (NOLOCK)
        WHERE CODIGO > %s
        ORDER BY CODIGO
        OFFSET 0 ROWS FETCH NEXT %s ROWS ONLY
    """

    def __init__(self, tamanho_chunk: int = 5_000) -> None:
        self._tamanho_chunk = tamanho_chunk

    def ler(
        self,
        conn: pymssql.Connection,
        sql_template: str,
        coluna_chave: str,
        mapear: Callable[[dict[str, Any]], Any],
        stop_event: threading.Event | None = None,
    ) -> Iterator[list[Any]]:
        """Itera em lotes até o resultado vir vazio ou incompleto."""
        ultimo = 0
        while True:
            if stop_event is not None and stop_event.is_set():
                return
            with conn.cursor(as_dict=True) as cur:
                cur.execute(sql_template, (ultimo, self._tamanho_chunk))
                rows: list[dict[str, Any]] = cur.fetchall()
            if not rows:
                return
            yield [mapear(r) for r in rows]
            if len(rows) < self._tamanho_chunk:
                return
            ultimo = int(rows[-1][coluna_chave])
