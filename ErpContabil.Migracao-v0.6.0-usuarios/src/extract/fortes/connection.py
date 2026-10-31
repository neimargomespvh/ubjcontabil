"""Fábrica de conexão com o SQL Server da Fortes Tecnologia."""
from __future__ import annotations

import contextlib
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pymssql

from src.domain.models.migration_options import FortesConnectionOptions


class FortesConnectionFactory:
    """Cria conexões curtas e identificáveis com o SQL Server da Fortes.

    Notes:
        - NÃO abrir um pool grande: o banco é do cliente. Abrir/fechar por chunk
          evita travar o ERP enquanto ele trabalha.
        - `appname` permite ao DBA identificar as sessões do migrador
          (SELECT * FROM sys.dm_exec_sessions WHERE program_name LIKE 'ERPContabil%').
        - `pymssql` (FreeTDS) é pure-Python + client nativo, mas NÃO usa string
          de conexão estilo ADO.NET; usamos kwargs. Se o servidor exigir
          `TrustServerCertificate`, instale `pyodbc` + ODBC Driver 18 e troque
          esta fábrica (interface se mantém).
    """

    def __init__(self, opt: FortesConnectionOptions) -> None:
        self._opt = opt

    def build_kwargs(self) -> dict[str, Any]:
        """Monta kwargs aceitos por `pymssql.connect(**kwargs)`."""
        return {
            "server": self._opt.host,
            "port": str(self._opt.porta),
            "user": self._opt.usuario,
            "password": self._opt.senha,
            "database": self._opt.database,
            "timeout": self._opt.timeout_conexao_s,
            "login_timeout": self._opt.timeout_conexao_s,
            "charset": "UTF-8",
            "appname": "ERPContabil-Migrador-Fortes",
        }

    def build_connection_string(self) -> str:
        """Representação legível para log — senha mascarada, não abre conexão."""
        return (
            f"mssql://{self._opt.usuario}:***@"
            f"{self._opt.host}:{self._opt.porta}/{self._opt.database}"
        )

    @contextlib.contextmanager
    def open(self) -> Iterator[pymssql.Connection]:
        """Abre a conexão e garante fechamento ao sair do bloco `with`."""
        import pymssql  # import tardio: só carrega FreeTDS quando precisa conectar

        conn = pymssql.connect(**self.build_kwargs())
        try:
            yield conn
        finally:
            conn.close()
