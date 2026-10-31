#!/usr/bin/env python3
"""fix_stage4.py — Corrige mypy/ruff do Stage 4 + path dos scripts.

Depois de rodar:
    pip install -r requirements-web.txt          # fastapi, uvicorn, jinja2, python-multipart
    docker run -d --name erp-pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:16
    python -m scripts.setup_db --ddl ddl/schema.sql
    python -m scripts.setup_db --ddl ddl/schema_stage3.sql
    python -m scripts.setup_db --ddl ddl/schema_stage4.sql
    pytest -q && mypy src/ && ruff check src/
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

G: dict[str, dict[str, str]] = {"code": {}, "scripts": {}, "config": {}}


# =====================================================================
#  CODE FIXES
# =====================================================================
G["code"]["src/web/auth.py"] = r'''"""Autenticação HTTP Basic para o painel Admin."""
from __future__ import annotations

import os
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

_security = HTTPBasic(auto_error=False)


def verificar_admin(
    creds: HTTPBasicCredentials | None = Depends(_security),
) -> str:
    """Valida `ADMIN_USER` + `ADMIN_PASSWORD`. Falha fechada se env faltar."""
    usuario_esperado = os.environ.get("ADMIN_USER", "admin")
    senha_esperada = os.environ.get("ADMIN_PASSWORD", "")

    if not senha_esperada:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ADMIN_PASSWORD não configurada no servidor",
        )

    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação obrigatória",
            headers={"WWW-Authenticate": "Basic"},
        )

    ok_user = secrets.compare_digest(str(creds.username), usuario_esperado)
    ok_senha = secrets.compare_digest(str(creds.password), senha_esperada)
    if not (ok_user and ok_senha):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
            headers={"WWW-Authenticate": "Basic"},
        )
    return str(creds.username)
'''


G["code"]["src/extract/fortes/participante_extractor.py"] = r'''"""Extrator de participantes (clientes/fornecedores) da Fortes."""
from __future__ import annotations

import threading
from collections.abc import Iterator
from typing import Any

from src.domain.contracts.extractor import IEntityExtractor
from src.domain.models.chunk import Chunk
from src.domain.models.entities.participante import ParticipanteOrigem
from src.extract.fortes.connection import FortesConnectionFactory
from src.extract.shared.sqlserver_chunk_reader import SqlServerChunkReader


class FortesParticipanteExtractor(IEntityExtractor[ParticipanteOrigem]):
    """Extrai PARTICIPANTE com WITH (NOLOCK) + keyset pagination."""

    _SQL = """
        SELECT  P.CODIGO, P.RAZAO_SOCIAL, P.NOME_FANTASIA, P.CNPJ_CPF,
                P.IE, P.IM, P.ENDERECO, P.CIDADE, P.UF, P.CEP,
                P.EMAIL, P.TELEFONE, P.TIPO_PESSOA
        FROM    dbo.PARTICIPANTE P WITH (NOLOCK)
        WHERE   P.CODIGO > %s
        ORDER BY P.CODIGO
        OFFSET 0 ROWS FETCH NEXT %s ROWS ONLY
    """

    def __init__(
        self, factory: FortesConnectionFactory, tamanho_chunk: int = 5_000
    ) -> None:
        self._factory = factory
        self._reader = SqlServerChunkReader(tamanho_chunk)

    def count_estimado(self) -> int | None:
        try:
            with (
                self._factory.open() as conn,
                conn.cursor() as cur,
            ):
                cur.execute(
                    "SELECT COUNT_BIG(*) FROM dbo.PARTICIPANTE WITH (NOLOCK)"
                )
                row = cur.fetchone()
                return int(str(row[0])) if row and row[0] is not None else None
        except Exception:
            return None

    def extract(
        self, stop_event: threading.Event | None = None
    ) -> Iterator[Chunk[ParticipanteOrigem]]:
        total = 0
        with self._factory.open() as conn:
            for lote in self._reader.ler(
                conn, self._SQL, "CODIGO", self._mapear, stop_event
            ):
                total += len(lote)
                yield Chunk(itens=lote, total_acumulado=total)

    @staticmethod
    def _mapear(r: Any) -> ParticipanteOrigem:
        return ParticipanteOrigem(
            codigo_origem=int(r["CODIGO"]),
            razao_social=r.get("RAZAO_SOCIAL"),
            nome_fantasia=r.get("NOME_FANTASIA"),
            documento=r.get("CNPJ_CPF"),
            inscricao_estadual=r.get("IE"),
            inscricao_municipal=r.get("IM"),
            endereco=r.get("ENDERECO"),
            cidade=r.get("CIDADE"),
            uf=r.get("UF"),
            cep=r.get("CEP"),
            email=r.get("EMAIL"),
            telefone=r.get("TELEFONE"),
            tipo_pessoa=r.get("TIPO_PESSOA"),
        )
'''


G["code"]["src/extract/fortes/empresa_extractor.py"] = r'''"""Extrator do cadastro de empresas da Fortes."""
from __future__ import annotations

import threading
from collections.abc import Iterator
from typing import Any

from src.domain.contracts.extractor import IEntityExtractor
from src.domain.models.chunk import Chunk
from src.domain.models.entities.empresa import EmpresaOrigem
from src.extract.fortes.connection import FortesConnectionFactory
from src.extract.shared.sqlserver_chunk_reader import SqlServerChunkReader


class FortesEmpresaExtractor(IEntityExtractor[EmpresaOrigem]):
    """Extrai EMPRESA com WITH (NOLOCK) + keyset pagination."""

    _SQL = """
        SELECT  E.CODIGO, E.RAZAO_SOCIAL, E.CNPJ, E.UF, E.REGIME_TRIBUTARIO
        FROM    dbo.EMPRESA E WITH (NOLOCK)
        WHERE   E.CODIGO > %s
        ORDER BY E.CODIGO
        OFFSET 0 ROWS FETCH NEXT %s ROWS ONLY
    """

    def __init__(
        self, factory: FortesConnectionFactory, tamanho_chunk: int = 5_000
    ) -> None:
        self._factory = factory
        self._reader = SqlServerChunkReader(tamanho_chunk)

    def count_estimado(self) -> int | None:
        try:
            with (
                self._factory.open() as conn,
                conn.cursor() as cur,
            ):
                cur.execute("SELECT COUNT_BIG(*) FROM dbo.EMPRESA WITH (NOLOCK)")
                row = cur.fetchone()
                return int(str(row[0])) if row and row[0] is not None else None
        except Exception:
            return None

    def extract(
        self, stop_event: threading.Event | None = None
    ) -> Iterator[Chunk[EmpresaOrigem]]:
        total = 0
        with self._factory.open() as conn:
            for lote in self._reader.ler(
                conn, self._SQL, "CODIGO", self._mapear, stop_event
            ):
                total += len(lote)
                yield Chunk(itens=lote, total_acumulado=total)

    @staticmethod
    def _mapear(r: Any) -> EmpresaOrigem:
        return EmpresaOrigem(
            codigo_origem=int(r["CODIGO"]),
            razao_social=r.get("RAZAO_SOCIAL"),
            cnpj=r.get("CNPJ"),
            uf=r.get("UF"),
            regime_tributario=r.get("REGIME_TRIBUTARIO"),
        )
'''


G["code"]["src/extract/fortes/plano_contas_extractor.py"] = r'''"""Extrator do plano de contas contábil da Fortes."""
from __future__ import annotations

import threading
from collections.abc import Iterator
from typing import Any

from src.domain.contracts.extractor import IEntityExtractor
from src.domain.models.chunk import Chunk
from src.domain.models.entities.conta_contabil import ContaContabil
from src.extract.fortes.connection import FortesConnectionFactory
from src.extract.shared.sqlserver_chunk_reader import SqlServerChunkReader


class FortesPlanoContasExtractor(IEntityExtractor[ContaContabil]):
    """Extrai PLANO_CONTAS (sintéticas + analíticas) da Fortes."""

    _SQL = """
        SELECT  P.CODIGO, P.NOME, P.CODIGO_PAI, P.NATUREZA, P.GRAU, P.NATUREZA_SALDO
        FROM    dbo.PLANO_CONTAS P WITH (NOLOCK)
        WHERE   P.CODIGO > %s
        ORDER BY P.CODIGO
        OFFSET 0 ROWS FETCH NEXT %s ROWS ONLY
    """

    def __init__(
        self, factory: FortesConnectionFactory, tamanho_chunk: int = 5_000
    ) -> None:
        self._factory = factory
        self._reader = SqlServerChunkReader(tamanho_chunk)

    def count_estimado(self) -> int | None:
        try:
            with (
                self._factory.open() as conn,
                conn.cursor() as cur,
            ):
                cur.execute(
                    "SELECT COUNT_BIG(*) FROM dbo.PLANO_CONTAS WITH (NOLOCK)"
                )
                row = cur.fetchone()
                return int(str(row[0])) if row and row[0] is not None else None
        except Exception:
            return None

    def extract(
        self, stop_event: threading.Event | None = None
    ) -> Iterator[Chunk[ContaContabil]]:
        total = 0
        with self._factory.open() as conn:
            for lote in self._reader.ler(
                conn, self._SQL, "CODIGO", self._mapear, stop_event
            ):
                total += len(lote)
                yield Chunk(itens=lote, total_acumulado=total)

    @staticmethod
    def _mapear(r: Any) -> ContaContabil:
        natureza = (r.get("NATUREZA") or "ANALITICA").upper()
        if natureza not in ("SINTETICA", "ANALITICA"):
            natureza = "SINTETICA" if natureza in ("S", "01", "1") else "ANALITICA"
        return ContaContabil(
            codigo=str(r["CODIGO"]),
            nome=r.get("NOME") or "(sem nome)",
            codigo_pai=r.get("CODIGO_PAI"),
            natureza=natureza,
            grau=int(r.get("GRAU") or 1),
            natureza_saldo=r.get("NATUREZA_SALDO"),
        )
'''


G["code"]["src/load/postgres_fallback_loader.py"] = r'''"""Fallback linha-a-linha com SAVEPOINT para o caso de COPY falhar."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import psycopg

from src.domain.models.entities.conta_contabil import ContaContabil
from src.domain.models.entities.empresa import EmpresaOrigem
from src.domain.models.entities.participante import ParticipanteDestino
from src.domain.models.entities.sped_registro import SpedRegistro
from src.infrastructure.logging.migration_logger import MigrationLogger

if TYPE_CHECKING:
    from psycopg import Connection


_INSERT_PARTICIPANTE = """
    INSERT INTO erp.participante (
        empresa_id, codigo_origem, origem_sistema, razao_social, nome_fantasia,
        documento, tipo_pessoa, inscricao_estadual, municipio, uf, cep, email, telefone
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (empresa_id, origem_sistema, codigo_origem) DO NOTHING
"""

_INSERT_EMPRESA = """
    INSERT INTO erp.empresa (
        empresa_id, codigo_origem, origem_sistema, razao_social, cnpj, uf, regime_tributario
    ) VALUES (%s, %s, 'FORTES', %s, %s, %s, %s)
    ON CONFLICT (empresa_id, origem_sistema, codigo_origem) DO NOTHING
"""

_INSERT_CONTA = """
    INSERT INTO erp.conta_contabil (
        empresa_id, codigo, nome, codigo_pai, natureza, grau, natureza_saldo
    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (empresa_id, codigo) DO NOTHING
"""

_INSERT_SPED = """
    INSERT INTO erp.sped_registro (
        empresa_id, arquivo, numero_linha, codigo, campos_json, linha_bruta
    ) VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (empresa_id, arquivo, numero_linha) DO NOTHING
"""


class PostgresFallbackRowLoader:
    """Insere linha a linha dentro de SAVEPOINTs, isolando registros ruins."""

    def __init__(self, logger: MigrationLogger) -> None:
        self._logger = logger

    def inserir_participantes(
        self,
        conn: Connection,
        tx: object | None,
        empresa_id: str,
        itens: list[ParticipanteDestino],
    ) -> int:
        return self._inserir(
            conn, _INSERT_PARTICIPANTE, "PARTICIPANTE",
            [
                (empresa_id, p.codigo_origem, p.origem_sistema, p.razao_social,
                 p.nome_fantasia, p.documento, p.tipo_pessoa, p.inscricao_estadual,
                 p.municipio, p.uf, p.cep, p.email, p.telefone)
                for p in itens
            ],
            [str(p.codigo_origem) for p in itens],
        )

    def inserir_empresas(
        self, conn: Connection, empresa_id: str, itens: list[EmpresaOrigem]
    ) -> int:
        return self._inserir(
            conn, _INSERT_EMPRESA, "EMPRESA",
            [
                (empresa_id, e.codigo_origem,
                 e.razao_social or "(sem razão social)",
                 (e.cnpj or "").strip(), e.uf, e.regime_tributario)
                for e in itens
            ],
            [str(e.codigo_origem) for e in itens],
        )

    def inserir_contas(
        self, conn: Connection, empresa_id: str, itens: list[ContaContabil]
    ) -> int:
        return self._inserir(
            conn, _INSERT_CONTA, "CONTA_CONTABIL",
            [
                (empresa_id, c.codigo, c.nome, c.codigo_pai,
                 c.natureza, c.grau, c.natureza_saldo)
                for c in itens
            ],
            [c.codigo for c in itens],
        )

    def inserir_sped(
        self, conn: Connection, empresa_id: str, itens: list[SpedRegistro]
    ) -> int:
        return self._inserir(
            conn, _INSERT_SPED, "SPED",
            [
                (empresa_id, r.arquivo, r.numero_linha, r.codigo,
                 json.dumps(list(r.campos), ensure_ascii=False), r.linha_bruta)
                for r in itens
            ],
            [f"{r.arquivo}:{r.numero_linha}" for r in itens],
        )

    def _inserir(
        self,
        conn: Connection,
        sql: str,
        entidade: str,
        rows: list[tuple[Any, ...]],
        ids: list[str],
    ) -> int:
        ok = 0
        for row, rid in zip(rows, ids, strict=True):
            try:
                with conn.transaction(), conn.cursor() as cur:
                    cur.execute(sql, row)
                ok += 1
            except psycopg.Error as e:
                self._logger.erro(entidade, rid, f"Falha no INSERT: {e!s}", e)
        return ok
'''


G["code"]["src/infrastructure/orchestrator.py"] = r'''"""Orquestrador: pipeline genérico (Empresa + Plano + Participante + SPED)."""
from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import psycopg

from src.domain.contracts.orchestrator import IMigrationOrchestrator
from src.domain.enums.enums import OperacaoSync, StatusMigracao
from src.domain.models.migration_options import FortesConnectionOptions
from src.domain.models.migration_progress import MigrationProgress
from src.domain.models.migration_result import MigrationResult
from src.extract.fortes.connection import FortesConnectionFactory
from src.extract.fortes.empresa_extractor import FortesEmpresaExtractor
from src.extract.fortes.participante_extractor import FortesParticipanteExtractor
from src.extract.fortes.plano_contas_extractor import FortesPlanoContasExtractor
from src.extract.tron.sped_txt_extractor import SpedTxtExtractor
from src.infrastructure.logging.migration_logger import MigrationLogger
from src.load.postgres_bulk_loader import PostgresBinaryBulkLoader
from src.load.postgres_fallback_loader import PostgresFallbackRowLoader
from src.load.sync_outbox_writer import SyncOutboxWriter
from src.transform.participante_transformer import ParticipanteTransformer
from src.transform.sped.transformers import (
    SpedR0150ToParticipante,
    SpedR0500ToContaContabil,
)


@dataclass(slots=True)
class _Etapa:
    nome: str
    entidade: str
    extractor: Any
    transformer: Any | None
    loader: Callable[[psycopg.Connection, str, list[Any]], int]
    fallback: Callable[[psycopg.Connection, str, list[Any]], int]
    sync: bool = True
    id_fn: Callable[[Any], str] = field(default=lambda _: "")


def _id_codigo_origem(item: Any) -> str:
    return str(item.codigo_origem)


def _id_codigo(item: Any) -> str:
    return str(item.codigo)


class MigrationOrchestrator(IMigrationOrchestrator):
    def __init__(
        self,
        conninfo: str,
        logger: MigrationLogger,
        bulk_loader: PostgresBinaryBulkLoader,
        fallback_loader: PostgresFallbackRowLoader,
        outbox: SyncOutboxWriter,
        transformer: ParticipanteTransformer,
    ) -> None:
        self._conninfo = conninfo
        self._logger = logger
        self._bulk = bulk_loader
        self._fallback = fallback_loader
        self._outbox = outbox
        self._transformer = transformer

    # -- loaders/fetchers tipados (evitam lambdas longas) -------------
    def _load_empresas(self, c: psycopg.Connection, eid: str, itens: list[Any]) -> int:
        return self._bulk.inserir_empresas(c, eid, itens)

    def _load_contas(self, c: psycopg.Connection, eid: str, itens: list[Any]) -> int:
        return self._bulk.inserir_contas(c, eid, itens)

    def _load_participantes(
        self, c: psycopg.Connection, eid: str, itens: list[Any]
    ) -> int:
        return self._bulk.inserir_participantes(c, None, eid, itens)

    def _load_sped(self, c: psycopg.Connection, eid: str, itens: list[Any]) -> int:
        return self._bulk.inserir_sped(c, eid, itens)

    def _fb_empresas(self, c: psycopg.Connection, eid: str, itens: list[Any]) -> int:
        return self._fallback.inserir_empresas(c, eid, itens)

    def _fb_contas(self, c: psycopg.Connection, eid: str, itens: list[Any]) -> int:
        return self._fallback.inserir_contas(c, eid, itens)

    def _fb_participantes(
        self, c: psycopg.Connection, eid: str, itens: list[Any]
    ) -> int:
        return self._fallback.inserir_participantes(c, None, eid, itens)

    def _fb_sped(self, c: psycopg.Connection, eid: str, itens: list[Any]) -> int:
        return self._fallback.inserir_sped(c, eid, itens)

    # -- Fortes ------------------------------------------------------
    def testar_conexao_fortes(self, opt: FortesConnectionOptions) -> bool:
        try:
            with (
                FortesConnectionFactory(opt).open() as conn,
                conn.cursor() as cur,
            ):
                cur.execute("SELECT 1")
            return True
        except Exception as e:
            self._logger.erro("CONEXAO", "-", "Falha ao conectar na Fortes", e)
            return False

    def executar_migracao_fortes(
        self,
        opt: FortesConnectionOptions,
        progresso: Callable[[MigrationProgress], None],
        etapas: Sequence[str] = ("empresa", "plano_contas", "participante"),
    ) -> MigrationResult:
        factory = FortesConnectionFactory(opt)
        configs = self._config_etapas_fortes(factory, opt, etapas)
        return self._executar(
            tipo="FORTES", empresa_id=opt.empresa_id or opt.database,
            etapas=configs, progresso=progresso,
        )

    # -- Arquivos (SPED auditoria) -----------------------------------
    def executar_migracao_arquivos(
        self,
        caminhos: list[str],
        empresa_id: str,
        progresso: Callable[[MigrationProgress], None],
    ) -> MigrationResult:
        etapas = [
            _Etapa(
                nome=f"sped:{Path(c).name}",
                entidade="sped_registro",
                extractor=SpedTxtExtractor(Path(c)),
                transformer=None,
                loader=self._load_sped,
                fallback=self._fb_sped,
                sync=False,
            )
            for c in caminhos
        ]
        return self._executar("SPED", empresa_id, etapas, progresso)

    # -- Arquivos (SPED estruturado) ---------------------------------
    def executar_migracao_sped_estruturada(
        self,
        caminhos: list[str],
        empresa_id: str,
        progresso: Callable[[MigrationProgress], None],
    ) -> MigrationResult:
        etapas: list[_Etapa] = []
        for c in caminhos:
            etapas.append(_Etapa(
                nome=f"sped-0150:{Path(c).name}",
                entidade="participante",
                extractor=SpedTxtExtractor(Path(c)),
                transformer=SpedR0150ToParticipante(),
                loader=self._load_participantes,
                fallback=self._fb_participantes,
                id_fn=_id_codigo_origem,
            ))
            etapas.append(_Etapa(
                nome=f"sped-0500:{Path(c).name}",
                entidade="conta_contabil",
                extractor=SpedTxtExtractor(Path(c)),
                transformer=SpedR0500ToContaContabil(),
                loader=self._load_contas,
                fallback=self._fb_contas,
                id_fn=_id_codigo,
            ))
        return self._executar("SPED-ESTRUTURADO", empresa_id, etapas, progresso)

    # -- pipeline genérico -------------------------------------------
    def _executar(
        self,
        tipo: str,
        empresa_id: str,
        etapas: list[_Etapa],
        progresso: Callable[[MigrationProgress], None],
    ) -> MigrationResult:
        job_id = str(uuid.uuid4())
        result = MigrationResult(job_id=job_id, empresa_id=empresa_id)
        inicio = time.time()
        self._logger.iniciar_job(job_id, tipo)
        progresso(MigrationProgress(etapa_atual=f"Conectando ({tipo})…"))

        try:
            with psycopg.connect(self._conninfo) as erp_conn:
                for etapa in etapas:
                    self._rodar_etapa(erp_conn, empresa_id, etapa, result, progresso)
            result.sucesso = True
            result.status = StatusMigracao.CONCLUIDO
            progresso(MigrationProgress(etapa_atual="Concluído", percentual=100.0))
        except Exception as e:
            result.status = StatusMigracao.FALHOU
            self._logger.erro("MIGRACAO", job_id, "Falha fatal", e)
            raise
        finally:
            result.duracao_segundos = time.time() - inicio
            self._logger.finalizar_job(job_id, result)
        return result

    def _rodar_etapa(
        self, erp_conn: psycopg.Connection, empresa_id: str,
        etapa: _Etapa, result: MigrationResult,
        progresso: Callable[[MigrationProgress], None],
    ) -> None:
        total_hint = self._total_hint(etapa.extractor)
        for chunk in self._iterar(etapa.extractor):
            validos = self._transformar(etapa, chunk.itens, result)
            if validos:
                with erp_conn.transaction():
                    try:
                        n = etapa.loader(erp_conn, empresa_id, validos)
                    except psycopg.Error as e_bulk:
                        self._logger.erro(
                            "BULK", etapa.nome,
                            f"COPY falhou ({e_bulk!s}); acionando fallback", e_bulk,
                        )
                        n = etapa.fallback(erp_conn, empresa_id, validos)
                    if etapa.sync and etapa.entidade:
                        ids = [etapa.id_fn(v) for v in validos]
                        self._outbox.enfileirar_batch(
                            erp_conn, empresa_id, etapa.entidade, ids,
                            OperacaoSync.UPSERT,
                        )
                    result.importados += n
            progresso(self._progresso(chunk, total_hint, etapa, result))

    @staticmethod
    def _total_hint(extractor: Any) -> int | None:
        if not callable(getattr(extractor, "count_estimado", None)):
            return None
        try:
            valor = extractor.count_estimado()
        except Exception:
            return None
        return cast(int | None, valor)

    @staticmethod
    def _iterar(extractor: Any) -> Iterable[Any]:
        return cast(Iterable[Any], extractor.extract())

    def _transformar(
        self, etapa: _Etapa, itens: list[Any], result: MigrationResult
    ) -> list[Any]:
        if etapa.transformer is None:
            return list(itens)
        validos: list[Any] = []
        for item in itens:
            t = etapa.transformer.transform(item)
            if t.sucesso and t.valor is not None:
                validos.append(t.valor)
            else:
                result.erros += 1
                rid = etapa.id_fn(item) or getattr(item, "codigo_origem", "?")
                self._logger.erro(etapa.entidade, str(rid), t.motivo or "?")
        return validos

    @staticmethod
    def _progresso(
        chunk: Any, total_hint: int | None, etapa: _Etapa, result: MigrationResult,
    ) -> MigrationProgress:
        pct = 0.0
        if total_hint:
            pct = min(99.0, 100.0 * chunk.total_acumulado / total_hint)
        return MigrationProgress(
            etapa_atual=f"Importando {etapa.nome}…",
            registros_processados=chunk.total_acumulado,
            registros_com_erro=result.erros,
            percentual=pct,
        )

    # -- config Fortes -----------------------------------------------
    def _config_etapas_fortes(
        self, factory: FortesConnectionFactory,
        opt: FortesConnectionOptions, etapas: Sequence[str],
    ) -> list[_Etapa]:
        mapa: dict[str, _Etapa] = {
            "empresa": _Etapa(
                nome="empresa", entidade="empresa",
                extractor=FortesEmpresaExtractor(factory, opt.tamanho_chunk),
                transformer=None,
                loader=self._load_empresas,
                fallback=self._fb_empresas,
                id_fn=_id_codigo_origem,
            ),
            "plano_contas": _Etapa(
                nome="plano_contas", entidade="conta_contabil",
                extractor=FortesPlanoContasExtractor(factory, opt.tamanho_chunk),
                transformer=None,
                loader=self._load_contas,
                fallback=self._fb_contas,
                id_fn=_id_codigo,
            ),
            "participante": _Etapa(
                nome="participante", entidade="participante",
                extractor=FortesParticipanteExtractor(factory, opt.tamanho_chunk),
                transformer=self._transformer,
                loader=self._load_participantes,
                fallback=self._fb_participantes,
                id_fn=_id_codigo_origem,
            ),
        }
        faltando = [n for n in etapas if n not in mapa]
        if faltando:
            raise ValueError(f"Etapas desconhecidas: {faltando}")
        return [mapa[n] for n in etapas]
'''


G["code"]["src/infrastructure/sync/sync_worker.py"] = r'''"""Worker que drena a outbox local e envia deltas para a nuvem."""
from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass
from typing import Any, cast

import psycopg
from psycopg.rows import dict_row

from src.infrastructure.sync.delta_client import DeltaClient

log = logging.getLogger(__name__)


_TABELAS: dict[str, tuple[str, str]] = {
    "participante":   ("erp.participante",    "codigo_origem"),
    "empresa":        ("erp.empresa",         "codigo_origem"),
    "conta_contabil": ("erp.conta_contabil",  "codigo"),
}

_LOTE_MAX_TENTATIVAS = 5
_BACKOFF_BASE_S = 30.0
_BACKOFF_MAX_S = 900.0


@dataclass(slots=True)
class _EventoOutbox:
    id: str
    empresa_id: str
    entidade: str
    operacao: str
    registro_id: str
    tentativas: int


class SyncWorker:
    """Drena `sync.sync_outbox` em lotes e envia para a nuvem."""

    def __init__(
        self,
        conninfo: str,
        base_url: str,
        api_key: str,
        batch_size: int = 100,
        poll_interval_s: float = 5.0,
        client: DeltaClient | None = None,
    ) -> None:
        self._conninfo = conninfo
        self._batch_size = batch_size
        self._poll = poll_interval_s
        self._client = client or DeltaClient(base_url, api_key)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # -- lifecycle ----------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="SyncWorker")
        self._thread.start()

    def stop(self, timeout_s: float = 10.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout_s)

    def _run(self) -> None:
        log.info("SyncWorker iniciado (intervalo %.1fs)", self._poll)
        while not self._stop.is_set():
            try:
                n = self.processar_um_lote()
                if n == 0:
                    self._stop.wait(self._poll)
                else:
                    log.info("Lote sincronizado: %d eventos", n)
            except Exception:
                log.exception("Erro no SyncWorker")
                self._stop.wait(self._poll * 2)

    # -- processamento -----------------------------------------------
    def processar_um_lote(self) -> int:
        """Processa até `batch_size` eventos pendentes. Retorna quantos OK."""
        with (
            psycopg.connect(self._conninfo, row_factory=dict_row) as conn,
            conn.transaction(),
        ):
            eventos = self._pegar_lote(conn)
            if not eventos:
                return 0

            por_empresa: dict[str, list[_EventoOutbox]] = {}
            for ev in eventos:
                por_empresa.setdefault(ev.empresa_id, []).append(ev)

            total_ok = 0
            for empresa_id, evs in por_empresa.items():
                ok, falhas = self._enviar_empresa(conn, empresa_id, evs)
                total_ok += ok
                self._marcar(conn, evs, falhas)
            return total_ok

    def _pegar_lote(
        self, conn: psycopg.Connection[dict[str, Any]]
    ) -> list[_EventoOutbox]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, empresa_id, entidade, operacao, registro_id, tentativas
                FROM sync.sync_outbox
                WHERE sincronizado_em IS NULL
                  AND agendado_para <= now()
                  AND tentativas < %s
                ORDER BY criado_em
                LIMIT %s
                FOR UPDATE SKIP LOCKED
                """,
                (_LOTE_MAX_TENTATIVAS, self._batch_size),
            )
            rows = cast(list[dict[str, Any]], cur.fetchall())
        return [
            _EventoOutbox(
                id=str(r["id"]), empresa_id=str(r["empresa_id"]),
                entidade=str(r["entidade"]), operacao=str(r["operacao"]),
                registro_id=str(r["registro_id"]),
                tentativas=int(r["tentativas"]),
            )
            for r in rows
        ]

    def _enviar_empresa(
        self, conn: psycopg.Connection[dict[str, Any]], empresa_id: str,
        eventos: list[_EventoOutbox],
    ) -> tuple[int, dict[str, str]]:
        payload_eventos: list[dict[str, Any]] = []
        for ev in eventos:
            if ev.operacao == "DELETE":
                payload_eventos.append({
                    "entidade": ev.entidade, "operacao": "DELETE",
                    "registro_id": ev.registro_id,
                })
                continue
            dados = self._buscar_dados(conn, ev)
            if dados is None:
                payload_eventos.append({
                    "entidade": ev.entidade, "operacao": "DELETE",
                    "registro_id": ev.registro_id,
                })
            else:
                payload_eventos.append({
                    "entidade": ev.entidade, "operacao": "UPSERT",
                    "registro_id": ev.registro_id, "dados": dados,
                })

        lote = {
            "lote_id": str(uuid.uuid4()),
            "empresa_id": empresa_id,
            "eventos": payload_eventos,
        }
        if self._client.enviar(lote):
            return len(eventos), {}
        return 0, {ev.id: "envio falhou" for ev in eventos}

    def _buscar_dados(
        self, conn: psycopg.Connection[dict[str, Any]], ev: _EventoOutbox,
    ) -> dict[str, Any] | None:
        tabela, coluna_chave = _TABELAS.get(ev.entidade, (None, None))
        if tabela is None:
            return None
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM {tabela} WHERE empresa_id = %s AND {coluna_chave} = %s",
                (ev.empresa_id, ev.registro_id),
            )
            row = cast(dict[str, Any] | None, cur.fetchone())
            return row

    def _marcar(
        self, conn: psycopg.Connection[dict[str, Any]], evs: list[_EventoOutbox],
        falhas: dict[str, str],
    ) -> None:
        with conn.cursor() as cur:
            for ev in evs:
                if ev.id not in falhas:
                    cur.execute(
                        "UPDATE sync.sync_outbox SET sincronizado_em = now() "
                        "WHERE id = %s",
                        (ev.id,),
                    )
                    continue

                novas = ev.tentativas + 1
                if novas >= _LOTE_MAX_TENTATIVAS:
                    cur.execute(
                        "INSERT INTO sync.sync_dlq "
                        "(id, empresa_id, entidade, operacao, registro_id, tentativas, erro) "
                        "SELECT id, empresa_id, entidade, operacao, registro_id, %s, %s "
                        "FROM sync.sync_outbox WHERE id = %s",
                        (novas, falhas[ev.id], ev.id),
                    )
                    cur.execute("DELETE FROM sync.sync_outbox WHERE id = %s", (ev.id,))
                else:
                    backoff = min(_BACKOFF_MAX_S, _BACKOFF_BASE_S * (2 ** novas))
                    cur.execute(
                        "UPDATE sync.sync_outbox SET tentativas = %s, "
                        "agendado_para = now() + (%s || ' seconds')::interval "
                        "WHERE id = %s",
                        (novas, str(int(backoff)), ev.id),
                    )
'''


G["code"]["src/web/app.py"] = r'''"""Painel Admin — Utilitários de Migração (FastAPI + Auth Basic)."""
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
        "utilitarios_migracao.html", {"request": request}
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
'''


# =====================================================================
#  SCRIPTS
# =====================================================================
_HEADER_PATH_FIX = (
    "from __future__ import annotations\n"
    "\n"
    "import sys\n"
    "from pathlib import Path\n"
    "\n"
    "# Garante que `from src...` funcione quando o script é executado\n"
    "# diretamente (python scripts/foo.py). Sem isso, sys.path[0] é\n"
    "# `scripts/`, e `src` não é encontrado.\n"
    "_ROOT = Path(__file__).resolve().parent.parent\n"
    "if str(_ROOT) not in sys.path:\n"
    "    sys.path.insert(0, str(_ROOT))\n"
)


G["scripts"]["scripts/run_sync_worker.py"] = r'''#!/usr/bin/env python3
"""Sobe o SyncWorker (processo separado do painel)."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import os
import signal
import time

from src.infrastructure.sync.sync_worker import SyncWorker


def main() -> int:
    conninfo = os.environ.get(
        "ERP_DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/erp_contabil",
    )
    cloud_url = os.environ.get("CLOUD_SYNC_URL", "")
    api_key = os.environ.get("CLOUD_SYNC_API_KEY", "")
    if not cloud_url or not api_key:
        print("❌ Configure CLOUD_SYNC_URL e CLOUD_SYNC_API_KEY", file=sys.stderr)
        return 1

    worker = SyncWorker(conninfo, cloud_url, api_key)
    worker.start()

    def _stop(signum: int, frame: object) -> None:
        print(f"\n⏹  Sinal {signum} — encerrando…")
        worker.stop()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    print("✓ SyncWorker rodando (Ctrl+C para parar)")
    while True:
        time.sleep(60)


if __name__ == "__main__":
    sys.exit(main())
'''


G["scripts"]["scripts/demo_fortes.py"] = r'''#!/usr/bin/env python3
"""Demo: executa a migração Fortes sem o painel web (CLI)."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import argparse
import os

from src.domain.models.migration_options import FortesConnectionOptions
from src.infrastructure.logging.migration_logger import MigrationLogger
from src.infrastructure.orchestrator import MigrationOrchestrator
from src.load.postgres_bulk_loader import PostgresBinaryBulkLoader
from src.load.postgres_fallback_loader import PostgresFallbackRowLoader
from src.load.sync_outbox_writer import SyncOutboxWriter
from src.transform.participante_transformer import ParticipanteTransformer


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", required=True)
    p.add_argument("--porta", type=int, default=1433)
    p.add_argument("--database", required=True)
    p.add_argument("--usuario", required=True)
    p.add_argument("--senha", required=True)
    p.add_argument("--empresa-id", required=True)
    p.add_argument("--etapas", default="empresa,plano_contas,participante")
    p.add_argument("--conninfo", default=os.environ.get(
        "ERP_DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/erp_contabil"))
    args = p.parse_args()

    opt = FortesConnectionOptions(
        host=args.host, porta=args.porta, database=args.database,
        usuario=args.usuario, senha=args.senha, empresa_id=args.empresa_id,
    )
    logger = MigrationLogger(Path("migracao_erros.log"), args.conninfo)
    orc = MigrationOrchestrator(
        conninfo=args.conninfo, logger=logger,
        bulk_loader=PostgresBinaryBulkLoader(args.conninfo),
        fallback_loader=PostgresFallbackRowLoader(logger),
        outbox=SyncOutboxWriter(),
        transformer=ParticipanteTransformer(),
    )

    print(f"🔌 Testando {args.host}:{args.porta}/{args.database}…")
    if not orc.testar_conexao_fortes(opt):
        print("❌ Falha na conexão. Ver migracao_erros.log.", file=sys.stderr)
        return 1
    print("✅ Conexão OK\n")

    etapas = tuple(e.strip() for e in args.etapas.split(","))

    def _cb(p: object) -> None:
        prog = getattr(p, "percentual", 0.0)
        etapa = getattr(p, "etapa_atual", "")
        print(f"  [{prog:5.1f}%] {etapa}")

    print(f"🚀 Migrando etapas: {etapas}\n")
    result = orc.executar_migracao_fortes(opt, _cb, etapas=etapas)
    print(f"\n{'✅' if result.sucesso else '❌'} "
          f"Importados: {result.importados} · Erros: {result.erros} · "
          f"Duração: {result.duracao_segundos:.1f}s")
    return 0 if result.sucesso else 1


if __name__ == "__main__":
    sys.exit(main())
'''


G["scripts"]["scripts/demo_sped.py"] = r'''#!/usr/bin/env python3
"""Demo: importa um arquivo .txt do SPED (auditoria)."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import argparse
import os

from src.infrastructure.logging.migration_logger import MigrationLogger
from src.infrastructure.orchestrator import MigrationOrchestrator
from src.load.postgres_bulk_loader import PostgresBinaryBulkLoader
from src.load.postgres_fallback_loader import PostgresFallbackRowLoader
from src.load.sync_outbox_writer import SyncOutboxWriter
from src.transform.participante_transformer import ParticipanteTransformer


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("arquivos", nargs="+", help="Arquivos .txt do SPED")
    p.add_argument("--empresa-id", required=True)
    p.add_argument("--conninfo", default=os.environ.get(
        "ERP_DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/erp_contabil"))
    args = p.parse_args()

    for arq in args.arquivos:
        if not Path(arq).exists():
            print(f"❌ Arquivo não encontrado: {arq}", file=sys.stderr)
            return 1

    logger = MigrationLogger(Path("migracao_erros.log"), args.conninfo)
    orc = MigrationOrchestrator(
        conninfo=args.conninfo, logger=logger,
        bulk_loader=PostgresBinaryBulkLoader(args.conninfo),
        fallback_loader=PostgresFallbackRowLoader(logger),
        outbox=SyncOutboxWriter(),
        transformer=ParticipanteTransformer(),
    )

    def _cb(p: object) -> None:
        prog = getattr(p, "percentual", 0.0)
        etapa = getattr(p, "etapa_atual", "")
        print(f"  [{prog:5.1f}%] {etapa}")

    print(f"🚀 Processando {len(args.arquivos)} arquivo(s)…\n")
    result = orc.executar_migracao_arquivos(args.arquivos, args.empresa_id, _cb)
    print(f"\n{'✅' if result.sucesso else '❌'} "
          f"Importados: {result.importados} · Erros: {result.erros}")
    return 0 if result.sucesso else 1


if __name__ == "__main__":
    sys.exit(main())
'''


G["scripts"]["scripts/demo_sped_transform.py"] = r'''#!/usr/bin/env python3
"""Demo: SPED estruturado (0150 → participante, 0500 → conta)."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import argparse
import os

from src.infrastructure.logging.migration_logger import MigrationLogger
from src.infrastructure.orchestrator import MigrationOrchestrator
from src.load.postgres_bulk_loader import PostgresBinaryBulkLoader
from src.load.postgres_fallback_loader import PostgresFallbackRowLoader
from src.load.sync_outbox_writer import SyncOutboxWriter
from src.transform.participante_transformer import ParticipanteTransformer


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("arquivos", nargs="+")
    p.add_argument("--empresa-id", required=True)
    p.add_argument("--conninfo", default=os.environ.get(
        "ERP_DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/erp_contabil"))
    args = p.parse_args()

    logger = MigrationLogger(Path("migracao_erros.log"), args.conninfo)
    orc = MigrationOrchestrator(
        conninfo=args.conninfo, logger=logger,
        bulk_loader=PostgresBinaryBulkLoader(args.conninfo),
        fallback_loader=PostgresFallbackRowLoader(logger),
        outbox=SyncOutboxWriter(),
        transformer=ParticipanteTransformer(),
    )

    def _cb(p: object) -> None:
        prog = getattr(p, "percentual", 0.0)
        etapa = getattr(p, "etapa_atual", "")
        print(f"  [{prog:5.1f}%] {etapa}")

    print(f"🚀 SPED estruturado: {len(args.arquivos)} arquivo(s)\n")
    result = orc.executar_migracao_sped_estruturada(
        args.arquivos, args.empresa_id, _cb,
    )
    print(f"\n{'✅' if result.sucesso else '❌'} "
          f"Importados: {result.importados} · Erros: {result.erros}")
    return 0 if result.sucesso else 1


if __name__ == "__main__":
    sys.exit(main())
'''


G["scripts"]["scripts/run_admin.sh"] = r'''#!/usr/bin/env bash
# Sobe o painel Admin com uvicorn.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v uvicorn >/dev/null 2>&1; then
    echo "❌ uvicorn não encontrado no PATH." >&2
    echo "   Rode: pip install -r requirements-web.txt" >&2
    exit 1
fi

if [ -z "${ADMIN_PASSWORD:-}" ]; then
    echo "⚠️  ADMIN_PASSWORD não definida. O painel vai recusar login (falha fechada)." >&2
    echo "   Defina: export ADMIN_PASSWORD='senha-forte-aqui'" >&2
fi

exec uvicorn src.web.app:app \
    --app-dir . \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --reload
'''


# =====================================================================
#  CONFIG
# =====================================================================
G["config"]["pyproject.toml"] = r'''[project]
name = "erp-contabil-migracao"
version = "0.4.1"
description = "Módulo de migração do ERP Contábil (Fortes / Tron / SPED)"
requires-python = ">=3.11"

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
asyncio_mode = "auto"
markers = ["integration: testes que exigem PostgreSQL real"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "SIM"]

[tool.ruff.lint.per-file-ignores]
"src/web/app.py"  = ["B008"]           # FastAPI Depends() em defaults
"src/web/auth.py" = ["B008"]           # HTTPBasic em defaults
"scripts/*.py"    = ["T201", "E402"]   # prints de CLI + sys.path fix antes dos imports
"tests/test_auth.py" = ["S105", "S106"]

[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "src.web.*"
disallow_untyped_decorators = false
'''


# =====================================================================
#  EXECUÇÃO
# =====================================================================
def _aplicar(
    root: Path, grupo: str, force: bool, backup: bool, dry_run: bool
) -> tuple[int, int, int]:
    criados = atualizados = pulados = 0
    for rel, content in G[grupo].items():
        dest = root / rel
        pfx = {"code": "🔧", "scripts": "📜", "config": "⚙️ "}[grupo]
        if not dest.exists():
            if dry_run:
                print(f"{pfx} [NOVO]      {rel}")
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content, encoding="utf-8")
                print(f"{pfx} [CRIADO]    {rel}")
            criados += 1
            continue
        if not force:
            print(f"{pfx} [SKIP]      {rel}")
            pulados += 1
            continue
        if dry_run:
            print(f"{pfx} [OVERWRITE] {rel}")
            atualizados += 1
            continue
        if backup:
            shutil.copy2(dest, dest.with_suffix(dest.suffix + ".bak"))
        dest.write_text(content, encoding="utf-8")
        print(f"{pfx} [UPDATED]   {rel}")
        atualizados += 1
    return criados, atualizados, pulados


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--only", choices=["code", "scripts", "config", "all"],
                        default="all")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"❌ Raiz inválida: {root}", file=sys.stderr)
        return 1
    if not args.force and not args.dry_run:
        print("⚠️  Use --dry-run ou --force --backup.\n")
        return 2

    print(f"📁 Raiz: {root}\n🎯 Grupos: {args.only}\n")
    grupos = list(G.keys()) if args.only == "all" else [args.only]
    tot_c = tot_a = tot_p = 0
    for g in grupos:
        print(f"── {g.upper()} ──")
        c, a, p = _aplicar(root, g, args.force, args.backup, args.dry_run)
        tot_c += c; tot_a += a; tot_p += p

    print(f"\n📊 Criados: {tot_c}, Atualizados: {tot_a}, Pulados: {tot_p}")
    if args.dry_run:
        print("(dry-run — nada foi escrito)")
        return 0

    print("\n" + "=" * 60)
    print("⚠️  INSTALAÇÃO DE DEPENDÊNCIAS (o mais importante):")
    print("=" * 60)
    print("  # 1. FastAPI + uvicorn + jinja2 + python-multipart")
    print("  pip install -r requirements-web.txt")
    print()
    print("  # 2. PostgreSQL (escolha uma opção):")
    print("  # A) Docker (recomendado):")
    print("  docker run -d --name erp-pg -e POSTGRES_PASSWORD=postgres \\")
    print("      -p 5432:5432 postgres:16")
    print("  # B) Nativo (Ubuntu/Debian):")
    print("  sudo apt install postgresql postgresql-contrib")
    print("  sudo systemctl start postgresql")
    print("  sudo -u postgres psql -c \"ALTER USER postgres PASSWORD 'postgres';\"")
    print()
    print("  # 3. Criar schema (aplica TODOS os DDLs em ordem):")
    print("  python -m scripts.setup_db --ddl ddl/schema.sql")
    print("  python -m scripts.setup_db --ddl ddl/schema_stage3.sql")
    print("  python -m scripts.setup_db --ddl ddl/schema_stage4.sql")
    print()
    print("  # 4. Configurar credenciais:")
    print("  export ADMIN_USER=admin")
    print("  export ADMIN_PASSWORD='senha-forte-aqui'")
    print("  export CLOUD_SYNC_URL='https://erp.example.com'")
    print("  export CLOUD_SYNC_API_KEY='chave-secreta'")
    print()
    print("  # 5. Verificação final:")
    print("  pytest -q && mypy src/ && ruff check src/")
    print()
    print("  # 6. Subir painel + worker:")
    print("  ./scripts/run_admin.sh                # terminal 1")
    print("  python scripts/run_sync_worker.py     # terminal 2")
    return 0


if __name__ == "__main__":
    sys.exit(main())