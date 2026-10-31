"""Contrato do motor de inserção de alta performance (Camada 4)."""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeVar

if TYPE_CHECKING:
    import psycopg

T = TypeVar("T")


class IEntityLoader(Protocol[T]):
    """Insere um lote de registros no PostgreSQL local."""

    def load(
        self,
        conn: psycopg.Connection,
        tx: psycopg.Transaction,
        empresa_id: str,
        itens: list[T],
    ) -> int:
        """Executa o INSERT em lote. Retorna quantos registros foram inseridos."""
        ...
