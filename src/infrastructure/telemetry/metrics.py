"""Métricas de execução do migrador."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class MigrationMetrics:
    """Contadores simples expostos ao painel Admin."""

    registros_lidos: int = 0
    registros_validos: int = 0
    registros_rejeitados: int = 0
    bytes_lidos: int = 0
    duracao_por_chunk_s: list[float] = field(default_factory=list)

    def registrar_chunk(self, lidos: int, validos: int, duracao_s: float) -> None:
        self.registros_lidos += lidos
        self.registros_validos += validos
        self.registros_rejeitados += lidos - validos
        self.duracao_por_chunk_s.append(duracao_s)

    @property
    def duracao_total_s(self) -> float:
        return sum(self.duracao_por_chunk_s)
