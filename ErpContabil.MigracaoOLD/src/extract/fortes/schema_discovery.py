"""Descoberta do schema real da Fortes antes de mapear colunas."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.extract.fortes.connection import FortesConnectionFactory


@dataclass(frozen=True, slots=True)
class TabelaDescoberta:
    """Metadado de uma coluna descoberta no SQL Server da Fortes."""

    table_schema: str
    table_name: str
    column_name: str
    data_type: str
    is_nullable: str


class FortesSchemaDiscovery:
    """Lista tabelas e colunas da Fortes para confirmar o De-Para na UI."""

    _SQL = """
        SELECT t.TABLE_SCHEMA, t.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE, c.IS_NULLABLE
        FROM INFORMATION_SCHEMA.TABLES t WITH (NOLOCK)
        JOIN INFORMATION_SCHEMA.COLUMNS c WITH (NOLOCK)
          ON c.TABLE_SCHEMA = t.TABLE_SCHEMA AND c.TABLE_NAME = t.TABLE_NAME
        WHERE t.TABLE_TYPE = 'BASE TABLE'
        ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME, c.ORDINAL_POSITION
    """

    def __init__(self, factory: FortesConnectionFactory) -> None:
        self._factory = factory

    def descobrir(self) -> list[TabelaDescoberta]:
        with (
            self._factory.open() as conn,
            conn.cursor(as_dict=True) as cur,
        ):
            cur.execute(self._SQL)
            rows: list[dict[str, Any]] = cur.fetchall()
        return [
            TabelaDescoberta(
                table_schema=r["TABLE_SCHEMA"],
                table_name=r["TABLE_NAME"],
                column_name=r["COLUMN_NAME"],
                data_type=r["DATA_TYPE"],
                is_nullable=r["IS_NULLABLE"],
            )
            for r in rows
        ]
