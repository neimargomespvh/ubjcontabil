"""Registro em memória de jobs de migração (para o painel Admin)."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.domain.enums.enums import StatusMigracao
from src.domain.models.migration_progress import MigrationProgress
from src.domain.models.migration_result import MigrationResult


@dataclass(slots=True)
class JobState:
    """Estado observável de um job em execução."""

    job_id: str
    tipo: str                     # "FORTES" | "SPED"
    descricao: str
    status: StatusMigracao = StatusMigracao.PENDENTE
    progresso: MigrationProgress = field(default_factory=MigrationProgress)
    resultado: MigrationResult | None = None
    erro: str | None = None
    iniciado_em: datetime = field(default_factory=lambda: datetime.now(UTC))
    finalizado_em: datetime | None = None


class JobRegistry:
    """Thread-safe registry in-memory. Suficiente para um painel single-process.

    Notes:
        Para produção multi-worker, trocar por Redis ou tabela Postgres.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, JobState] = {}

    def criar(self, job_id: str, tipo: str, descricao: str) -> JobState:
        with self._lock:
            state = JobState(job_id=job_id, tipo=tipo, descricao=descricao)
            state.status = StatusMigracao.EM_ANDAMENTO
            self._jobs[job_id] = state
            return state

    def atualizar_progresso(self, job_id: str, progresso: MigrationProgress) -> None:
        with self._lock:
            if (state := self._jobs.get(job_id)) is not None:
                state.progresso = progresso

    def finalizar(self, job_id: str, resultado: MigrationResult) -> None:
        with self._lock:
            if (state := self._jobs.get(job_id)) is not None:
                state.resultado = resultado
                state.status = (
                    StatusMigracao.CONCLUIDO
                    if resultado.sucesso
                    else StatusMigracao.FALHOU
                )
                state.finalizado_em = datetime.now(UTC)

    def falhar(self, job_id: str, mensagem: str) -> None:
        with self._lock:
            if (state := self._jobs.get(job_id)) is not None:
                state.erro = mensagem
                state.status = StatusMigracao.FALHOU
                state.finalizado_em = datetime.now(UTC)

    def obter(self, job_id: str) -> JobState | None:
        with self._lock:
            return self._jobs.get(job_id)

    def listar(self, limite: int = 50) -> list[JobState]:
        with self._lock:
            return list(self._jobs.values())[-limite:]
