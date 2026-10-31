"""Leitor de blocos do SPED (0000, 0150, C100...)."""
from __future__ import annotations

from collections.abc import Iterable, Iterator

from src.domain.models.entities.sped_registro import SpedRegistro


class SpedBlockReader:
    """Filtra registros do SPED por bloco (prefixo do código)."""

    def __init__(self, registros: Iterable[SpedRegistro]) -> None:
        self._registros = registros

    def por_bloco(self, bloco: str) -> Iterator[SpedRegistro]:
        """Retorna apenas registros cujo código começa pelo bloco (ex.: 'C')."""
        for r in self._registros:
            if r.codigo.startswith(bloco):
                yield r
