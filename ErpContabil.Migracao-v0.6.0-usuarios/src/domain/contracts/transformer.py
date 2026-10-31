"""Contrato do motor de transformação (Camada 3)."""
from __future__ import annotations

from typing import Protocol, TypeVar

from src.domain.models.chunk import TransformResult

S = TypeVar("S", contravariant=True)
D = TypeVar("D")


class IEntityTransformer(Protocol[S, D]):
    """Transforma e valida um registro origem → destino.

    Notes:
        `S` é contravariante (só aparece em parâmetro) e `D` invariante
        (aparece em `TransformResult[D]`, que é uma dataclass genérica).
        Sem o `contravariant=True`, mypy strict acusa
        "Invariant type variable S used in protocol where contravariant one is expected".
    """

    def transform(self, origem: S) -> TransformResult[D]:
        """Aplica De-Para, normalizações e validações contábeis.

        Returns:
            TransformResult.ok(destino) se válido, ou
            TransformResult.falha(motivo) — caso em que o registro vai para quarentena.
        """
        ...
