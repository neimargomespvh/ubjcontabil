"""Painel Admin — Utilitários de Migração (FastAPI + Auth Basic)."""
from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.domain.models.migration_options import FortesConnectionOptions
from src.infrastructure.job_registry import JobRegistry
from src.infrastructure.logging.migration_logger import MigrationLogger
from src.infrastructure.orchestrator import MigrationOrchestrator
from src.load.postgres_bulk_loader import PostgresBinaryBulkLoader
from src.load.postgres_fallback_loader import PostgresFallbackRowLoader
from src.load.sync_outbox_writer import SyncOutboxWriter
from src.transform.participante_transformer import ParticipanteTransformer
from src.web.auth import verificar_admin
from src.web.schemas import (
    ArquivoUploadResponse,
    FortesIniciarRequest,
    FortesTestarRequest,
    JobResponse,
    SpedEstruturadoRequest,
    StatusResponse,
    SyncStatusResponse,
)

CONNINFO = os.environ.get(
    "ERP_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/erp_contabil",
)
UPLOAD_DIR = Path(os.environ.get("MIGRACAO_UPLOAD_DIR", "uploads"))
LOG_PATH = Path(os.environ.get("MIGRACAO_LOG", "migracao_erros.log"))

app = FastAPI(title="ERP Contábil — Admin")
templates = Jinja2Templates(directory="src/web/templates")
app.mount("/static", StaticFiles(directory="src/web/static"), name="static")

_registry = JobRegistry()
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="migracao")
_orc: MigrationOrchestrator | None = None
_orc_err: str | None = None


def _get_orc() -> MigrationOrchestrator:
    global _orc, _orc_err
    if _orc is not None:
        return _orc
    if _orc_err is not None:
        raise HTTPException(500, _orc_err)
    try:
        logger = MigrationLogger(LOG_PATH, CONNINFO)
        _orc = MigrationOrchestrator(
            conninfo=CONNINFO, logger=logger,
            bulk_loader=PostgresBinaryBulkLoader(CONNINFO),
            fallback_loader=PostgresFallbackRowLoader(logger),
            outbox=SyncOutboxWriter(),
            transformer=ParticipanteTransformer(),
        )
        return _orc
    except Exception as e:
        _orc_err = f"Falha ao construir orquestrador: {e}"
        raise HTTPException(500, _orc_err) from e


# -- páginas protegidas -------------------------------------------
@app.get("/admin/utilitarios/migracao", response_class=HTMLResponse)
def pagina_migracao(
    request: Request, _user: str = Depends(verificar_admin),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="utilitarios_migracao.html",
    )

@app.get("/api/migracao/health")
def health() -> dict[str, Any]:
    try:
        _get_orc()
        return {"status": "ok", "db": CONNINFO.split("@")[-1]}
    except HTTPException as e:
        return {"status": "erro", "detalhe": e.detail}


# -- Fortes ------------------------------------------------------
@app.post("/api/migracao/fortes/testar")
def testar_fortes(
    req: FortesTestarRequest, _user: str = Depends(verificar_admin),
) -> dict[str, bool]:
    return {"ok": _get_orc().testar_conexao_fortes(_to_options(req))}


@app.post("/api/migracao/fortes/iniciar", response_model=JobResponse)
def iniciar_fortes(
    req: FortesIniciarRequest, _user: str = Depends(verificar_admin),
) -> JobResponse:
    orc = _get_orc()
    job_id = str(uuid.uuid4())
    _registry.criar(job_id, "FORTES", f"Fortes → {req.database}")
    opt = _to_options(req)
    opt.tamanho_chunk = req.tamanho_chunk

    def _run() -> None:
        try:
            r = orc.executar_migracao_fortes(
                opt, lambda p: _registry.atualizar_progresso(job_id, p),
                etapas=tuple(req.etapas),
            )
            _registry.finalizar(job_id, r)
        except Exception as e:
            _registry.falhar(job_id, str(e))

    _executor.submit(_run)
    return JobResponse(job_id=job_id, status="EM_ANDAMENTO",
                       descricao=f"Fortes → {req.database}")


# -- Arquivos ----------------------------------------------------
@app.post("/api/migracao/arquivos/upload", response_model=ArquivoUploadResponse)
async def upload_arquivos(
    empresa_id: str, arquivos: list[UploadFile],
    _user: str = Depends(verificar_admin),
) -> ArquivoUploadResponse:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    salvos: list[str] = []
    for f in arquivos:
        if not f.filename or not f.filename.endswith((".txt", ".xml")):
            continue
        destino = UPLOAD_DIR / f"{uuid.uuid4().hex}_{f.filename}"
        destino.write_bytes(await f.read())
        salvos.append(str(destino))
    return ArquivoUploadResponse(arquivos=salvos, empresa_id=empresa_id)


@app.post("/api/migracao/arquivos/iniciar", response_model=JobResponse)
def iniciar_arquivos(
    empresa_id: str, caminhos: list[str],
    _user: str = Depends(verificar_admin),
) -> JobResponse:
    orc = _get_orc()
    if not caminhos:
        raise HTTPException(400, "Nenhum arquivo informado")
    job_id = str(uuid.uuid4())
    _registry.criar(job_id, "SPED", f"{len(caminhos)} arquivo(s)")

    def _run() -> None:
        try:
            r = orc.executar_migracao_arquivos(
                caminhos, empresa_id,
                lambda p: _registry.atualizar_progresso(job_id, p),
            )
            _registry.finalizar(job_id, r)
        except Exception as e:
            _registry.falhar(job_id, str(e))

    _executor.submit(_run)
    return JobResponse(job_id=job_id, status="EM_ANDAMENTO",
                       descricao=f"{len(caminhos)} arquivo(s)")


@app.post("/api/migracao/arquivos/estruturado", response_model=JobResponse)
def iniciar_sped_estruturado(
    req: SpedEstruturadoRequest, _user: str = Depends(verificar_admin),
) -> JobResponse:
    orc = _get_orc()
    if not req.caminhos:
        raise HTTPException(400, "Nenhum arquivo informado")
    job_id = str(uuid.uuid4())
    _registry.criar(job_id, "SPED-ESTRUTURADO", f"{len(req.caminhos)} arquivo(s)")

    def _run() -> None:
        try:
            r = orc.executar_migracao_sped_estruturada(
                req.caminhos, req.empresa_id,
                lambda p: _registry.atualizar_progresso(job_id, p),
            )
            _registry.finalizar(job_id, r)
        except Exception as e:
            _registry.falhar(job_id, str(e))

    _executor.submit(_run)
    return JobResponse(
        job_id=job_id, status="EM_ANDAMENTO",
        descricao=f"SPED estruturado ({len(req.caminhos)} arquivo(s))",
    )


# -- Status de job -----------------------------------------------
@app.get("/api/migracao/status/{job_id}", response_model=StatusResponse)
def status(job_id: str, _user: str = Depends(verificar_admin)) -> StatusResponse:
    state = _registry.obter(job_id)
    if state is None:
        raise HTTPException(404, f"Job {job_id} não encontrado")
    r = state.resultado
    return StatusResponse(
        job_id=state.job_id, tipo=state.tipo, status=state.status.value,
        etapa_atual=state.progresso.etapa_atual,
        percentual=state.progresso.percentual,
        registros_processados=state.progresso.registros_processados,
        registros_com_erro=state.progresso.registros_com_erro,
        importados=r.importados if r else 0,
        erros=r.erros if r else 0,
        erro=state.erro,
        iniciado_em=state.iniciado_em.isoformat(),
        finalizado_em=state.finalizado_em.isoformat() if state.finalizado_em else None,
    )


# -- Status do sync ----------------------------------------------
_SQL_SYNC_STATUS = """
    SELECT
        COUNT(*) FILTER (
            WHERE sincronizado_em IS NULL
              AND agendado_para <= now()
              AND tentativas < 5
        ) AS pendentes,
        COUNT(*) FILTER (
            WHERE sincronizado_em IS NULL
              AND agendado_para > now()
        ) AS agendados,
        COUNT(*) FILTER (
            WHERE sincronizado_em IS NULL
              AND tentativas >= 5
        ) AS com_erro,
        COUNT(*) FILTER (
            WHERE sincronizado_em > now() - interval '24 hours'
        ) AS sincronizados_24h
    FROM sync.sync_outbox
"""


@app.get("/api/migracao/sync/status", response_model=SyncStatusResponse)
def sync_status(_user: str = Depends(verificar_admin)) -> SyncStatusResponse:
    with psycopg.connect(CONNINFO, autocommit=True) as conn:
        row = conn.execute(_SQL_SYNC_STATUS).fetchone()
        if row is None:
            return SyncStatusResponse(
                pendentes=0, agendados=0, com_erro=0,
                sincronizados_24h=0, dlq_total=0,
            )
        dlq = conn.execute("SELECT COUNT(*) FROM sync.sync_dlq").fetchone()
    return SyncStatusResponse(
        pendentes=int(row[0]), agendados=int(row[1]),
        com_erro=int(row[2]), sincronizados_24h=int(row[3]),
        dlq_total=int(dlq[0]) if dlq else 0,
    )


@app.get("/api/migracao/jobs")
def listar_jobs(_user: str = Depends(verificar_admin)) -> JSONResponse:
    return JSONResponse([
        {"job_id": s.job_id, "tipo": s.tipo, "status": s.status.value,
         "iniciado_em": s.iniciado_em.isoformat(), "descricao": s.descricao}
        for s in _registry.listar()
    ])


def _to_options(req: FortesTestarRequest) -> FortesConnectionOptions:
    return FortesConnectionOptions(
        host=req.host, porta=req.porta, database=req.database,
        usuario=req.usuario, senha=req.senha, empresa_id=req.empresa_id,
    )
