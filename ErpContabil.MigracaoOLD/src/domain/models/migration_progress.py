"""Modelo de progresso reportado à UI do Admin."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MigrationProgress:
    """Instantâneo do progresso de uma migração."""

    etapa_atual: str = ""
    registros_processados: int = 0
    registros_com_erro: int = 0
    percentual: float = 0.0
