"""Enumerações do domínio de migração."""
from __future__ import annotations

from enum import StrEnum


class OperacaoSync(StrEnum):
    """Operação a ser propagada para o Sincronizador Delta."""

    UPSERT = "UPSERT"
    DELETE = "DELETE"


class SeveridadeErro(StrEnum):
    """Severidade de um erro registrado no log de migração."""

    INFO = "INFO"
    AVISO = "AVISO"
    ERRO = "ERRO"
    FATAL = "FATAL"


class StatusMigracao(StrEnum):
    """Estado de um job de migração."""

    PENDENTE = "PENDENTE"
    EM_ANDAMENTO = "EM_ANDAMENTO"
    CONCLUIDO = "CONCLUIDO"
    CONCLUIDO_COM_ERROS = "CONCLUIDO_COM_ERROS"
    FALHOU = "FALHOU"
    CANCELADO = "CANCELADO"
