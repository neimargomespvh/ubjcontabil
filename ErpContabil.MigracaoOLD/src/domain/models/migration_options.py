"""Opções de configuração das migrações."""
from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field


class FortesConnectionOptions(BaseModel):
    """Credenciais e endpoint do SQL Server da Fortes Tecnologia."""

    host: str
    porta: int = 1433
    database: str
    usuario: str
    senha: str
    empresa_id: str = ""              # ID da empresa no ERP destino (chave do outbox)
    trust_server_certificate: bool = False
    timeout_conexao_s: int = 10
    tamanho_chunk: int = Field(default=5_000, ge=100, le=50_000)


@dataclass(frozen=True, slots=True)
class MigrationOptions:
    """Opções gerais de uma execução de migração."""

    empresa_id: str
    origem: str
    dry_run: bool = False
    parar_no_primeiro_erro: bool = False
    caminho_log: str = "migracao_erros.log"
    caminho_quarentena: str = "migracao_quarentena.jsonl"
