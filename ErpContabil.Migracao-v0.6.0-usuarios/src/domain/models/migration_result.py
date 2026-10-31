"""Resultado consolidado de um job de migração."""
from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.enums.enums import StatusMigracao


@dataclass(slots=True)
class MigrationResult:
    """Resumo final de um job de migração."""

    job_id: str
    empresa_id: str
    sucesso: bool = False
    status: StatusMigracao = StatusMigracao.PENDENTE
    importados: int = 0
    erros: int = 0
    ignorados: int = 0
    duracao_segundos: float = 0.0
    log: list[str] = field(default_factory=list)
