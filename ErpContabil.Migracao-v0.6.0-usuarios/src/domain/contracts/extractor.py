"""Contrato do motor de extração (Camada 2)."""
from __future__ import annotations

import threading
from collections.abc import Iterator
from typing import Protocol, TypeVar

from src.domain.models.chunk import Chunk

T = TypeVar("T")


class IEntityExtractor(Protocol[T]):
    """Extrai registros de uma base de origem em lotes (chunks).

    Notes:
        - `stop_event`: evento sinalizado externamente para interromper a extração.
        - Todo extrator é `Iterator` (streaming) — nunca carrega a tabela inteira em RAM.
        - A paginação por keyset (`WHERE id > @ultimo`) é responsabilidade da implementação.
    """

    def extract(
        self, stop_event: threading.Event | None = None
    ) -> Iterator[Chunk[T]]:
        """Itera sobre os registros em lotes de até `tamanho_chunk`."""
        ...
