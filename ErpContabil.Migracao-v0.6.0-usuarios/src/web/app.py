"""Painel Admin — Utilitários de Migração (FastAPI + JWT / Basic)."""
from __future__ import annotations

import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
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
from src.web.auth import (
    CurrentUser,
    RequireAdmin,
    RequireLeitura,
    RequireOperador,
    TokenResponse,
    UsuarioCreate,
    UsuarioResponse,
    UsuarioUpdate,
    audit,
    get_current_user,
    get_user_repo,
    login_basic,
    login_form,
    usuario_to_response,
)
from src.web.schemas import (
    ArquivoUploadResponse,
    FortesIniciarRequest,
    FortesTestarRequest,
    JobResponse,
    SpedEstruturadoRequest,
    StatusResponse,
    SyncStatusResponse,
)

log = logging.getLogger("migracao.web")

CONNINFO = os.environ.get(
    "ERP_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/erp_contabil",
)
UPLOAD_DIR = Path(os.environ.get("MIGRACAO_UPLOAD_DIR", "uploads"))
LOG_PATH = Path(os.environ.get("MIGRACAO_LOG", "migracao_erros.log"))

_registry = JobRegistry()
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="migracao")
_orc: MigrationOrchestrator | None = None
_orc_err: str | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):  # noqa: ANN201
    log.info("Admin panel starting (db=%s)", CONNINFO.split("@")[-1] if "@" in CONNINFO else "?")
    try:
        get_user_repo().ensure_bootstrap_admin()
    except Exception:
        log.exception("Bootstrap de usuários falhou (tabela pode ainda não existir)")
    yield
    _executor.shutdown(wait=False)
    log.info("Admin panel stopped")


app = FastAPI(
    title="ERP Contábil — Admin",
    version="0.5.0",
    lifespan=lifespan,
)
templates = Jinja2Templates(directory="src/web/templates")
app.mount("/static", StaticFiles(directory="src/web/static"), name="static")


def _get_orc() -> MigrationOrchestrator:
    global _orc, _orc_err
    if _orc is not None:
        return _orc
    if _orc_err is not None:
        raise HTTPException(500, _orc_err)
    try:
        logger = MigrationLogger(LOG_PATH, CONNINFO)
        _orc = MigrationOrchestrator(
            conninfo=CONNINFO,
            logger=logger,
            bulk_loader=PostgresBinaryBulkLoader(CONNINFO),
            fallback_loader=PostgresFallbackRowLoader(logger),
            outbox=SyncOutboxWriter(),
            transformer=ParticipanteTransformer(),
        )
        return _orc
    except Exception as e:
        _orc_err = f"Falha ao construir orquestrador: {e}"
        raise HTTPException(500, _orc_err) from e


def _to_options(req: FortesTestarRequest) -> FortesConnectionOptions:
    return FortesConnectionOptions(
        host=req.host,
        porta=req.porta,
        database=req.database,
        usuario=req.usuario,
        senha=req.senha,
        empresa_id=req.empresa_id,
    )


# ---------------------------------------------------------------------------
# Health & Auth
# ---------------------------------------------------------------------------
@app.get("/api/migracao/health")
def health() -> dict[str, Any]:
    """Healthcheck público (usado por Docker / load balancer)."""
    try:
        with psycopg.connect(CONNINFO, connect_timeout=3) as conn:
            conn.execute("SELECT 1")
        db_ok = True
    except Exception as exc:
        db_ok = False
        return {"status": "degraded", "db": False, "detail": str(exc)[:200]}
    return {"status": "ok", "db": db_ok, "version": "0.5.0"}


@app.post("/api/auth/login", response_model=TokenResponse)
def api_login(token: TokenResponse = Depends(login_basic)) -> TokenResponse:
    """Troca Basic Auth por JWT. Use o token no header Authorization: Bearer <token>."""
    return token


@app.post("/api/auth/token", response_model=TokenResponse)
def api_login_form(token: TokenResponse = Depends(login_form)) -> TokenResponse:
    """Login form (username/password) — compatível com OAuth2PasswordRequestForm / Swagger."""
    return token


@app.get("/api/auth/me", response_model=UsuarioResponse)
def api_me(user: CurrentUser = Depends(get_current_user)) -> UsuarioResponse:
    """Retorna o usuário autenticado."""
    repo = get_user_repo()
    u = repo.get_by_id(user.id)
    if u is None:
        # token válido mas usuário removido — devolve claims mínimas
        return UsuarioResponse(
            id=user.id, username=user.username, role=user.role,
            nome=user.nome, ativo=True,
        )
    return usuario_to_response(u)


# ---------------------------------------------------------------------------
# Gestão de usuários (somente admin)
# ---------------------------------------------------------------------------
@app.get("/api/usuarios", response_model=list[UsuarioResponse])
def listar_usuarios(_admin: RequireAdmin) -> list[UsuarioResponse]:
    return [usuario_to_response(u) for u in get_user_repo().list_all()]


@app.post("/api/usuarios", response_model=UsuarioResponse, status_code=201)
def criar_usuario(
    body: UsuarioCreate,
    request: Request,
    admin: RequireAdmin,
) -> UsuarioResponse:
    repo = get_user_repo()
    if repo.get_by_username(body.username) is not None:
        raise HTTPException(409, f"Username já existe: {body.username}")
    try:
        u = repo.create(body.username, body.password, body.role, body.nome)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    audit("USER_CREATE", admin.username, detail=f"user={u.username} role={u.role}", request=request)
    return usuario_to_response(u)


@app.patch("/api/usuarios/{user_id}", response_model=UsuarioResponse)
def atualizar_usuario(
    user_id: str,
    body: UsuarioUpdate,
    request: Request,
    admin: RequireAdmin,
) -> UsuarioResponse:
    repo = get_user_repo()
    if repo.get_by_id(user_id) is None:
        raise HTTPException(404, "Usuário não encontrado")
    try:
        u = repo.update(
            user_id,
            role=body.role,
            nome=body.nome,
            ativo=body.ativo,
            password=body.password,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    audit("USER_UPDATE", admin.username, detail=f"user_id={user_id}", request=request)
    return usuario_to_response(u)


@app.delete("/api/usuarios/{user_id}", status_code=204)
def remover_usuario(
    user_id: str,
    request: Request,
    admin: RequireAdmin,
) -> None:
    repo = get_user_repo()
    target = repo.get_by_id(user_id)
    if target is None:
        raise HTTPException(404, "Usuário não encontrado")
    if target.id == admin.id:
        raise HTTPException(400, "Não é permitido remover o próprio usuário")
    repo.delete(user_id)
    audit("USER_DELETE", admin.username, detail=f"user_id={user_id} username={target.username}", request=request)


# ---------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------
@app.get("/admin/utilitarios/migracao", response_class=HTMLResponse)
def pagina_migracao(
    request: Request,
    user: RequireLeitura,
) -> HTMLResponse:
    audit("VIEW_ADMIN", user.username, request=request)
    return templates.TemplateResponse(
        request=request,
        name="utilitarios_migracao.html",
    )


# ---------------------------------------------------------------------------
# Fortes
# ---------------------------------------------------------------------------
@app.post("/api/migracao/fortes/testar")
def testar_fortes(
    req: FortesTestarRequest,
    request: Request,
    user: RequireOperador,
) -> dict[str, bool]:
    audit("FORTES_TEST", user.username, detail=f"{req.host}/{req.database}", request=request)
    return {"ok": _get_orc().testar_conexao_fortes(_to_options(req))}


@app.post("/api/migracao/fortes/iniciar", response_model=JobResponse)
def iniciar_fortes(
    req: FortesIniciarRequest,
    request: Request,
    user: RequireOperador,
) -> JobResponse:
    orc = _get_orc()
    job_id = str(uuid.uuid4())
    _registry.criar(job_id, "FORTES", f"Fortes → {req.database}")
    opt = _to_options(req)
    opt.tamanho_chunk = req.tamanho_chunk
    audit(
        "FORTES_START",
        user.username,
        detail=f"job={job_id} db={req.database} etapas={req.etapas}",
        request=request,
    )

    def _run() -> None:
        try:
            r = orc.executar_migracao_fortes(
                opt,
                lambda p: _registry.atualizar_progresso(job_id, p),
                etapas=tuple(req.etapas),
            )
            _registry.finalizar(job_id, r)
        except Exception as e:
            _registry.falhar(job_id, str(e))

    _executor.submit(_run)
    return JobResponse(
        job_id=job_id,
        status="EM_ANDAMENTO",
        descricao=f"Fortes → {req.database}",
    )


# ---------------------------------------------------------------------------
# Arquivos / SPED
# ---------------------------------------------------------------------------
@app.post("/api/migracao/arquivos/upload", response_model=ArquivoUploadResponse)
async def upload_arquivos(
    empresa_id: str,
    arquivos: list[UploadFile],
    request: Request,
    user: RequireOperador,
) -> ArquivoUploadResponse:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    salvos: list[str] = []
    for f in arquivos:
        if not f.filename or not f.filename.endswith((".txt", ".xml")):
            continue
        destino = UPLOAD_DIR / f"{uuid.uuid4().hex}_{f.filename}"
        destino.write_bytes(await f.read())
        salvos.append(str(destino))
    audit(
        "UPLOAD",
        user.username,
        detail=f"empresa={empresa_id} n={len(salvos)}",
        request=request,
    )
    return ArquivoUploadResponse(arquivos=salvos, empresa_id=empresa_id)


@app.post("/api/migracao/arquivos/iniciar", response_model=JobResponse)
def iniciar_arquivos(
    empresa_id: str,
    caminhos: list[str],
    request: Request,
    user: RequireOperador,
) -> JobResponse:
    orc = _get_orc()
    if not caminhos:
        raise HTTPException(400, "Nenhum arquivo informado")
    job_id = str(uuid.uuid4())
    _registry.criar(job_id, "SPED", f"{len(caminhos)} arquivo(s)")
    audit(
        "SPED_START",
        user.username,
        detail=f"job={job_id} empresa={empresa_id} n={len(caminhos)}",
        request=request,
    )

    def _run() -> None:
        try:
            r = orc.executar_migracao_arquivos(
                caminhos,
                empresa_id,
                lambda p: _registry.atualizar_progresso(job_id, p),
            )
            _registry.finalizar(job_id, r)
        except Exception as e:
            _registry.falhar(job_id, str(e))

    _executor.submit(_run)
    return JobResponse(
        job_id=job_id,
        status="EM_ANDAMENTO",
        descricao=f"{len(caminhos)} arquivo(s)",
    )


@app.post("/api/migracao/arquivos/estruturado", response_model=JobResponse)
def iniciar_sped_estruturado(
    req: SpedEstruturadoRequest,
    request: Request,
    user: RequireOperador,
) -> JobResponse:
    orc = _get_orc()
    if not req.caminhos:
        raise HTTPException(400, "Nenhum arquivo informado")
    job_id = str(uuid.uuid4())
    _registry.criar(job_id, "SPED-ESTRUTURADO", f"{len(req.caminhos)} arquivo(s)")
    audit(
        "SPED_ESTRUTURADO_START",
        user.username,
        detail=f"job={job_id} empresa={req.empresa_id}",
        request=request,
    )

    def _run() -> None:
        try:
            r = orc.executar_migracao_sped_estruturada(
                req.caminhos,
                req.empresa_id,
                lambda p: _registry.atualizar_progresso(job_id, p),
            )
            _registry.finalizar(job_id, r)
        except Exception as e:
            _registry.falhar(job_id, str(e))

    _executor.submit(_run)
    return JobResponse(
        job_id=job_id,
        status="EM_ANDAMENTO",
        descricao=f"SPED estruturado ({len(req.caminhos)} arquivo(s))",
    )


# ---------------------------------------------------------------------------
# Status / Jobs / Sync
# ---------------------------------------------------------------------------
@app.get("/api/migracao/status/{job_id}", response_model=StatusResponse)
def status(job_id: str, user: RequireLeitura) -> StatusResponse:
    state = _registry.obter(job_id)
    if state is None:
        raise HTTPException(404, f"Job {job_id} não encontrado")
    r = state.resultado
    return StatusResponse(
        job_id=state.job_id,
        tipo=state.tipo,
        status=state.status.value,
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
def sync_status(user: RequireLeitura) -> SyncStatusResponse:
    with psycopg.connect(CONNINFO, autocommit=True) as conn:
        row = conn.execute(_SQL_SYNC_STATUS).fetchone()
        if row is None:
            return SyncStatusResponse(
                pendentes=0, agendados=0, com_erro=0,
                sincronizados_24h=0, dlq_total=0,
            )
        try:
            dlq = conn.execute("SELECT COUNT(*) FROM sync.sync_dlq").fetchone()
            dlq_total = int(dlq[0]) if dlq else 0
        except Exception:
            dlq_total = 0
    return SyncStatusResponse(
        pendentes=int(row[0]),
        agendados=int(row[1]),
        com_erro=int(row[2]),
        sincronizados_24h=int(row[3]),
        dlq_total=dlq_total,
    )


@app.get("/api/migracao/jobs")
def listar_jobs(user: RequireLeitura) -> JSONResponse:
    return JSONResponse([
        {
            "job_id": s.job_id,
            "tipo": s.tipo,
            "status": s.status.value,
            "iniciado_em": s.iniciado_em.isoformat(),
            "descricao": s.descricao,
        }
        for s in _registry.listar()
    ])
