"""Conexão Firebird com a Tron (opções + listagem de tabelas)."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TronConnectionOptions:
    """Credenciais do Firebird da Tron."""

    host: str
    database: str
    usuario: str
    senha: str
    porta: int = 3050
    charset: str = "UTF8"


class TronFirebirdExtractor:
    """Wrapper de conexão — extração real fica em `tron_extractor.TronExtractor`."""

    def __init__(self, opt: TronConnectionOptions) -> None:
        self._opt = opt

    @contextmanager
    def conectar(self) -> Iterator[Any]:
        from firebird.driver import connect

        dsn = f"{self._opt.host}/{self._opt.porta}:{self._opt.database}"
        conn = connect(
            dsn, user=self._opt.usuario, password=self._opt.senha,
            charset=self._opt.charset,
        )
        try:
            yield conn
        finally:
            conn.close()

    def listar_tabelas(self) -> list[str]:
        with self.conectar() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT TRIM(RDB$RELATION_NAME) FROM RDB$RELATIONS "
                "WHERE RDB$SYSTEM_FLAG = 0 ORDER BY 1"
            )
            return [str(r[0]).strip() for r in cur.fetchall()]
