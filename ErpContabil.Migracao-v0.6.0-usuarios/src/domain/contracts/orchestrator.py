"""Contrato do orquestrador de migração."""
from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from src.domain.models.migration_options import FortesConnectionOptions
from src.domain.models.migration_progress import MigrationProgress
from src.domain.models.migration_result import MigrationResult


class IMigrationOrchestrator(Protocol):
    """Coordena Extract → Transform → Load e publica eventos no outbox."""

    def testar_conexao_fortes(self, opt: FortesConnectionOptions) -> bool:
        """Testa rapidamente a conexão com o SQL Server da Fortes."""
        ...

    def executar_migracao_fortes(
        self,
        opt: FortesConnectionOptions,
        progresso: Callable[[MigrationProgress], None],
    ) -> MigrationResult:
        """Executa o pipeline completo para a origem Fortes."""
        ...

    def executar_migracao_arquivos(
        self,
        caminhos: list[str],
        empresa_id: str,
        progresso: Callable[[MigrationProgress], None],
    ) -> MigrationResult:
        """Executa o pipeline a partir de arquivos .txt (SPED) e/ou .xml (NF-e)."""
        ...
