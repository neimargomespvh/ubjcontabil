"""Modelos de agregação usados pelos motores de ETL."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar

T = TypeVar("T")
U = TypeVar("U")


@dataclass(frozen=True, slots=True)
class Chunk(Generic[T]):
    """Lote de registros extraídos da origem.

    Attributes:
        itens: registros do lote (tipicamente 5.000).
        total_acumulado: quantos registros já foram extraídos desde o início.
    """

    itens: list[T]
    total_acumulado: int


@dataclass(frozen=True, slots=True)
class TransformResult(Generic[U]):
    """Resultado de uma transformação — sucesso (com valor) ou falha (com motivo)."""

    sucesso: bool
    valor: U | None = None
    motivo: str | None = None

    @classmethod
    def ok(cls, valor: U) -> TransformResult[U]:
        """Cria um resultado de sucesso."""
        return cls(sucesso=True, valor=valor)

    @classmethod
    def falha(cls, motivo: str) -> TransformResult[U]:
        """Cria um resultado de falha (vai para quarentena)."""
        return cls(sucesso=False, motivo=motivo)


@dataclass(frozen=True, slots=True)
class ResultadoValidacaoPlano:
    """Resultado da validação contábil do plano de contas."""

    valido: bool
    erros: list[str] = field(default_factory=list)
