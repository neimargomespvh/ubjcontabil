"""Modelos Pydantic para a API do painel Admin."""
from __future__ import annotations

from pydantic import BaseModel, Field


class FortesTestarRequest(BaseModel):
    host: str
    porta: int = 1433
    database: str
    usuario: str
    senha: str
    empresa_id: str = ""


class FortesIniciarRequest(FortesTestarRequest):
    etapas: list[str] = Field(
        default_factory=lambda: ["empresa", "plano_contas", "participante"]
    )
    tamanho_chunk: int = 5_000


class SpedEstruturadoRequest(BaseModel):
    empresa_id: str
    caminhos: list[str]


class JobResponse(BaseModel):
    job_id: str
    status: str
    descricao: str


class StatusResponse(BaseModel):
    job_id: str
    tipo: str
    status: str
    etapa_atual: str
    percentual: float
    registros_processados: int
    registros_com_erro: int
    importados: int
    erros: int
    erro: str | None = None
    iniciado_em: str
    finalizado_em: str | None = None


class ArquivoUploadResponse(BaseModel):
    arquivos: list[str]
    empresa_id: str


class SyncStatusResponse(BaseModel):
    pendentes: int
    agendados: int
    com_erro: int
    sincronizados_24h: int
    dlq_total: int
