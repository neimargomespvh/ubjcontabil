#!/usr/bin/env python3
"""implement_stage2.py — Pipeline FORTES completo (Stage 2).

Implementa 10 arquivos + 1 DDL:
  · model    → migration_options.py (adiciona empresa_id)
  · logger   → migration_logger.py         (JSONL + tabela migracao.erro)
  · extract  → sqlserver_chunk_reader.py, participante_extractor.py
  · transform→ participante_transformer.py, validators/participante.py
  · load     → postgres_bulk_loader.py, postgres_fallback_loader.py,
               sync_outbox_writer.py
  · infra    → orchestrator.py             (pipeline ponta-a-ponta)
  · ddl      → ddl/schema.sql              (tabelas erp/sync/migracao)

Uso:
    python implement_stage2.py --dry-run
    python implement_stage2.py --force --backup

Depois:
    psql -d erp_contabil -f ddl/schema.sql      # criar tabelas
    pytest -v && mypy src/ && ruff check src/
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

GRUPO: dict[str, dict[str, str]] = {"model": {}, "impl": {}, "ddl": {}}


# ---------------------------------------------------------------------
#  GRUPO "model"
# ---------------------------------------------------------------------
GRUPO["model"]["src/domain/models/migration_options.py"] = r'''"""Opções de configuração das migrações."""
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
'''


# ---------------------------------------------------------------------
#  GRUPO "impl"
# ---------------------------------------------------------------------
GRUPO["impl"]["src/infrastructure/logging/migration_logger.py"] = r'''"""Logger resiliente (JSONL + tabela migracao.erro)."""
from __future__ import annotations

import json
import socket
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg

from src.domain.models.migration_result import MigrationResult


class MigrationLogger:
    """Grava cada erro em arquivo JSONL e (best-effort) na tabela migracao.erro.

    Notes:
        - Thread-safe via `threading.Lock` — o arquivo é a fonte de auditoria.
        - Se o INSERT no banco falhar, o erro JÁ está no arquivo (nunca perde).
        - Abre/fecha conexão por erro: erros são raros, simplicidade vence.
    """

    def __init__(self, caminho_log: Path, connection_string: str) -> None:
        self._caminho_log = caminho_log
        self._connection_string = connection_string
        self._lock = threading.Lock()

    def iniciar_job(self, job_id: str, origem: str) -> None:
        """Registra o início do job no arquivo e em migracao.job."""
        self._escrever({
            "evento": "inicio_job", "job_id": job_id, "origem": origem,
            "ts": datetime.now(timezone.utc).isoformat(),
            "maquina": socket.gethostname(),
        })
        self._executar_sql(
            "INSERT INTO migracao.job (id, origem) VALUES (%s, %s) "
            "ON CONFLICT (id) DO NOTHING",
            (job_id, origem),
        )

    def erro(
        self,
        entidade: str,
        registro_id: str,
        mensagem: str,
        excecao: BaseException | None = None,
    ) -> None:
        """Grava linha JSONL + INSERT em migracao.erro."""
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "entidade": entidade,
            "registro_id": registro_id,
            "mensagem": mensagem,
            "stack": str(excecao) if excecao else None,
            "maquina": socket.gethostname(),
        }
        self._escrever(payload)
        self._executar_sql(
            "INSERT INTO migracao.erro (entidade, registro_id, mensagem, stack) "
            "VALUES (%s, %s, %s, %s)",
            (entidade, registro_id, mensagem, payload["stack"]),
        )

    def finalizar_job(self, job_id: str, resultado: MigrationResult) -> None:
        """Marca o job como concluído em migracao.job e no arquivo."""
        self._escrever({
            "evento": "fim_job", "job_id": job_id,
            "sucesso": resultado.sucesso, "status": resultado.status.value,
            "importados": resultado.importados, "erros": resultado.erros,
            "duracao_s": resultado.duracao_segundos,
        })
        self._executar_sql(
            "UPDATE migracao.job SET finalizado_em = now(), sucesso = %s, "
            "importados = %s, erros = %s, duracao_s = %s WHERE id = %s",
            (resultado.sucesso, resultado.importados, resultado.erros,
             resultado.duracao_segundos, job_id),
        )

    # -- internos -----------------------------------------------------
    def _escrever(self, payload: dict[str, Any]) -> None:
        linha = json.dumps(payload, ensure_ascii=False) + "\n"
        with self._lock:
            self._caminho_log.parent.mkdir(parents=True, exist_ok=True)
            with self._caminho_log.open("a", encoding="utf-8") as f:
                f.write(linha)

    def _executar_sql(self, sql: str, params: tuple[Any, ...]) -> None:
        try:
            with psycopg.connect(self._connection_string, autocommit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
        except Exception:
            pass  # arquivo já tem o registro — auditoria preservada
'''


GRUPO["impl"]["src/extract/shared/sqlserver_chunk_reader.py"] = r'''"""Paginação por keyset para SQL Server (chunks de N registros)."""
from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from typing import Any

import pymssql


class SqlServerChunkReader:
    """Lê tabelas grandes em lotes com keyset pagination.

    O `sql_template` DEVE conter dois placeholders `%s`:
      - 1º: último valor da chave (inicia em 0)
      - 2º: tamanho do lote (LIMIT / FETCH NEXT)

    Exemplo:
        SELECT CODIGO, NOME FROM TABELA WITH (NOLOCK)
        WHERE CODIGO > %s
        ORDER BY CODIGO
        OFFSET 0 ROWS FETCH NEXT %s ROWS ONLY
    """

    def __init__(self, tamanho_chunk: int = 5_000) -> None:
        self._tamanho_chunk = tamanho_chunk

    def ler(
        self,
        conn: pymssql.Connection,
        sql_template: str,
        coluna_chave: str,
        mapear: Callable[[dict[str, Any]], Any],
        stop_event: threading.Event | None = None,
    ) -> Iterator[list[Any]]:
        """Itera em lotes até o resultado vir vazio ou incompleto."""
        ultimo = 0
        while True:
            if stop_event is not None and stop_event.is_set():
                return
            with conn.cursor(as_dict=True) as cur:
                cur.execute(sql_template, (ultimo, self._tamanho_chunk))
                rows: list[dict[str, Any]] = cur.fetchall()
            if not rows:
                return
            yield [mapear(r) for r in rows]
            if len(rows) < self._tamanho_chunk:
                return
            ultimo = int(rows[-1][coluna_chave])
'''


GRUPO["impl"]["src/extract/fortes/participante_extractor.py"] = r'''"""Extrator de participantes (clientes/fornecedores) da Fortes."""
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
        """Contagem rápida para estimar percentual; None se falhar."""
        try:
            with self._factory.open() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT COUNT_BIG(*) FROM dbo.PARTICIPANTE WITH (NOLOCK)"
                    )
                    row = cur.fetchone()
                    return int(row[0]) if row else None
        except Exception:
            return None

    def extract(
        self, stop_event: threading.Event | None = None
    ) -> Iterator[Chunk[ParticipanteOrigem]]:
        """Itera sobre PARTICIPANTE em lotes."""
        total = 0
        with self._factory.open() as conn:
            for lote in self._reader.ler(
                conn, self._SQL, "CODIGO", self._mapear, stop_event
            ):
                total += len(lote)
                yield Chunk(itens=lote, total_acumulado=total)

    @staticmethod
    def _mapear(r: dict[str, Any]) -> ParticipanteOrigem:
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


GRUPO["impl"]["src/transform/validators/participante.py"] = r'''"""Validação de participantes antes do load."""
from __future__ import annotations

from src.domain.models.entities.participante import ParticipanteDestino


class ParticipanteValidator:
    """Regras de negócio sobre um participante já normalizado."""

    @staticmethod
    def validar(p: ParticipanteDestino) -> tuple[bool, str | None]:
        """Valida razão social, documento e UF."""
        if not p.razao_social or not p.razao_social.strip():
            return False, "Razão social vazia"
        if not p.documento or len(p.documento) not in (11, 14):
            return False, f"Documento com tamanho inválido ({len(p.documento or '')})"
        if p.uf is not None and len(p.uf) != 2:
            return False, f"UF inválida: {p.uf!r}"
        return True, None
'''


GRUPO["impl"]["src/transform/participante_transformer.py"] = r'''"""Transformer participante origem → destino."""
from __future__ import annotations

from src.domain.contracts.transformer import IEntityTransformer
from src.domain.models.chunk import TransformResult
from src.domain.models.entities.participante import (
    ParticipanteDestino,
    ParticipanteOrigem,
)
from src.transform.mappings.fortes_para_erp_map import FortesParaErpMap
from src.transform.normalizers.normalizers import Normalizers
from src.transform.validators.cpf_cnpj import CpfCnpjValidator
from src.transform.validators.participante import ParticipanteValidator


class ParticipanteTransformer(
    IEntityTransformer[ParticipanteOrigem, ParticipanteDestino]
):
    """Aplica De-Para, normalizações e valida CPF/CNPJ."""

    def transform(
        self, origem: ParticipanteOrigem
    ) -> TransformResult[ParticipanteDestino]:
        tipo = FortesParaErpMap.tipo_pessoa(origem.tipo_pessoa)
        ok, motivo = CpfCnpjValidator.validar(origem.documento, tipo)
        if not ok:
            return TransformResult.falha(motivo or "Documento inválido")

        destino = ParticipanteDestino(
            codigo_origem=origem.codigo_origem,
            razao_social=Normalizers.texto(origem.razao_social) or "(sem razão social)",
            nome_fantasia=Normalizers.texto(origem.nome_fantasia),
            documento=CpfCnpjValidator.somente_digitos(origem.documento),
            tipo_pessoa=tipo,
            inscricao_estadual=Normalizers.documento(origem.inscricao_estadual),
            municipio=Normalizers.texto(origem.cidade),
            uf=Normalizers.uf(origem.uf),
            cep=Normalizers.documento(origem.cep),
            email=Normalizers.email(origem.email),
            telefone=Normalizers.telefone(origem.telefone),
            origem_sistema="FORTES",
        )
        ok, motivo = ParticipanteValidator.validar(destino)
        if not ok:
            return TransformResult.falha(motivo or "Falha de validação")
        return TransformResult.ok(destino)
'''


GRUPO["impl"]["src/load/postgres_bulk_loader.py"] = r'''"""Bulk Insert no PostgreSQL via COPY ... FROM STDIN (FORMAT BINARY)."""
from __future__ import annotations

from typing import TYPE_CHECKING

import psycopg
from psycopg import sql

from src.domain.models.entities.participante import ParticipanteDestino

if TYPE_CHECKING:
    from psycopg import Connection


_COPY_SQL = sql.SQL(
    "COPY erp.participante ("
    "  empresa_id, codigo_origem, origem_sistema, razao_social, nome_fantasia,"
    "  documento, tipo_pessoa, inscricao_estadual, municipio, uf, cep, email, telefone"
    ") FROM STDIN (FORMAT BINARY)"
)

_TIPOS = ["text", "int8", "text", "text", "text", "text", "text",
          "text", "text", "text", "text", "text", "text"]


class PostgresBinaryBulkLoader:
    """Insere grandes volumes via COPY BINARY (3–10× mais rápido que INSERT).

    Notes:
        COPY é tudo-ou-nada no lote. Se o COPY falhar, o orquestrador
        aciona PostgresFallbackRowLoader (savepoints linha-a-linha).
    """

    def __init__(self, connection_string: str) -> None:
        self._connection_string = connection_string

    def inserir_participantes(
        self,
        conn: Connection,
        tx: object | None,
        empresa_id: str,
        itens: list[ParticipanteDestino],
    ) -> int:
        """Executa COPY BINARY e retorna quantas linhas foram enviadas."""
        with conn.cursor() as cur:
            with cur.copy(_COPY_SQL) as copy:
                copy.set_types(_TIPOS)
                for p in itens:
                    copy.write_row((
                        empresa_id,
                        p.codigo_origem,
                        p.origem_sistema,
                        p.razao_social,
                        p.nome_fantasia,
                        p.documento,
                        p.tipo_pessoa,
                        p.inscricao_estadual,
                        p.municipio,
                        p.uf,
                        p.cep,
                        p.email,
                        p.telefone,
                    ))
        return len(itens)
'''


GRUPO["impl"]["src/load/postgres_fallback_loader.py"] = r'''"""Fallback linha-a-linha com SAVEPOINT."""
from __future__ import annotations

from typing import TYPE_CHECKING

import psycopg

from src.domain.models.entities.participante import ParticipanteDestino
from src.infrastructure.logging.migration_logger import MigrationLogger

if TYPE_CHECKING:
    from psycopg import Connection


_INSERT_SQL = """
    INSERT INTO erp.participante (
        empresa_id, codigo_origem, origem_sistema, razao_social, nome_fantasia,
        documento, tipo_pessoa, inscricao_estadual, municipio, uf, cep, email, telefone
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (empresa_id, origem_sistema, codigo_origem) DO NOTHING
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
        """Retorna quantos registros foram inseridos com sucesso."""
        ok = 0
        for p in itens:
            try:
                with conn.transaction():    # vira SAVEPOINT se já houver tx aberta
                    with conn.cursor() as cur:
                        cur.execute(_INSERT_SQL, (
                            empresa_id, p.codigo_origem, p.origem_sistema,
                            p.razao_social, p.nome_fantasia, p.documento,
                            p.tipo_pessoa, p.inscricao_estadual, p.municipio,
                            p.uf, p.cep, p.email, p.telefone,
                        ))
                ok += 1
            except psycopg.Error as e:
                self._logger.erro(
                    "PARTICIPANTE", str(p.codigo_origem),
                    f"Falha no INSERT: {e!s}", e,
                )
        return ok
'''


GRUPO["impl"]["src/load/sync_outbox_writer.py"] = r'''"""Transactional Outbox para o Sincronizador Delta."""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.domain.enums.enums import OperacaoSync

if TYPE_CHECKING:
    from psycopg import Connection


_INSERT_SQL = """
    INSERT INTO sync.sync_outbox (entidade, registro_id, operacao)
    VALUES (%s, %s, %s)
"""


class SyncOutboxWriter:
    """Enfileira eventos na MESMA transação do Load."""

    def enfileirar(
        self,
        conn: Connection,
        tx: object | None,
        entidade: str,
        registro_id: str,
        operacao: OperacaoSync,
    ) -> None:
        """INSERT em sync.sync_outbox (mesma tx do Load)."""
        with conn.cursor() as cur:
            cur.execute(_INSERT_SQL, (entidade, registro_id, operacao.value))
'''


GRUPO["impl"]["src/infrastructure/orchestrator.py"] = r'''"""Orquestrador: Extract → Transform → Load + Outbox (pipeline FORTES)."""
from __future__ import annotations

import time
import uuid
from collections.abc import Callable

import psycopg

from src.domain.contracts.orchestrator import IMigrationOrchestrator
from src.domain.enums.enums import OperacaoSync, StatusMigracao
from src.domain.models.migration_options import FortesConnectionOptions
from src.domain.models.migration_progress import MigrationProgress
from src.domain.models.migration_result import MigrationResult
from src.extract.fortes.connection import FortesConnectionFactory
from src.extract.fortes.participante_extractor import FortesParticipanteExtractor
from src.infrastructure.logging.migration_logger import MigrationLogger
from src.load.postgres_bulk_loader import PostgresBinaryBulkLoader
from src.load.postgres_fallback_loader import PostgresFallbackRowLoader
from src.load.sync_outbox_writer import SyncOutboxWriter
from src.transform.participante_transformer import ParticipanteTransformer


class MigrationOrchestrator(IMigrationOrchestrator):
    """Coordena o pipeline ponta-a-ponta."""

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

    def testar_conexao_fortes(self, opt: FortesConnectionOptions) -> bool:
        try:
            with FortesConnectionFactory(opt).open() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            return True
        except Exception as e:
            self._logger.erro("CONEXAO", "-", "Falha ao conectar na Fortes", e)
            return False

    def executar_migracao_fortes(
        self,
        opt: FortesConnectionOptions,
        progresso: Callable[[MigrationProgress], None],
    ) -> MigrationResult:
        job_id = str(uuid.uuid4())
        empresa_id = opt.empresa_id or opt.database
        result = MigrationResult(job_id=job_id, empresa_id=empresa_id)
        inicio = time.time()

        self._logger.iniciar_job(job_id, "FORTES")
        progresso(MigrationProgress(etapa_atual="Conectando à Fortes…"))

        factory = FortesConnectionFactory(opt)
        extractor = FortesParticipanteExtractor(factory, opt.tamanho_chunk)
        total_hint = extractor.count_estimado()

        try:
            with psycopg.connect(self._conninfo) as erp_conn:
                for chunk in extractor.extract():
                    self._processar_chunk(erp_conn, chunk.itens, empresa_id, result)

                    pct = 0.0
                    if total_hint:
                        pct = min(99.0, 100.0 * chunk.total_acumulado / total_hint)
                    progresso(MigrationProgress(
                        etapa_atual="Importando participantes…",
                        registros_processados=chunk.total_acumulado,
                        registros_com_erro=result.erros,
                        percentual=pct,
                    ))

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

    def executar_migracao_arquivos(
        self,
        caminhos: list[str],
        empresa_id: str,
        progresso: Callable[[MigrationProgress], None],
    ) -> MigrationResult:
        raise NotImplementedError("TODO Stage 3: pipeline SPED/Tron")

    # -- internos -----------------------------------------------------
    def _processar_chunk(
        self,
        erp_conn: psycopg.Connection,
        itens: list[object],
        empresa_id: str,
        result: MigrationResult,
    ) -> None:
        from src.domain.models.entities.participante import ParticipanteOrigem

        validos = []
        for item in itens:
            assert isinstance(item, ParticipanteOrigem)
            t = self._transformer.transform(item)
            if t.sucesso and t.valor is not None:
                validos.append(t.valor)
            else:
                result.erros += 1
                self._logger.erro(
                    "PARTICIPANTE", str(item.codigo_origem), t.motivo or "?",
                )

        if not validos:
            return

        with erp_conn.transaction():
            try:
                n = self._bulk.inserir_participantes(
                    erp_conn, None, empresa_id, validos
                )
            except psycopg.Error as e_bulk:
                self._logger.erro(
                    "BULK", "chunk",
                    f"COPY falhou ({e_bulk!s}); acionando fallback", e_bulk,
                )
                n = self._fallback.inserir_participantes(
                    erp_conn, None, empresa_id, validos
                )
            self._outbox.enfileirar(
                erp_conn, None, "participante", empresa_id, OperacaoSync.UPSERT
            )
            result.importados += n
'''


# ---------------------------------------------------------------------
#  GRUPO "ddl"
# ---------------------------------------------------------------------
GRUPO["ddl"]["ddl/schema.sql"] = r'''-- =========================================================
-- ERP Contábil — Schema mínimo para o migrador
-- Rodar:  psql -d erp_contabil -f ddl/schema.sql
-- =========================================================
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS erp;
CREATE SCHEMA IF NOT EXISTS sync;
CREATE SCHEMA IF NOT EXISTS migracao;

-- erp.participante
CREATE TABLE IF NOT EXISTS erp.participante (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id         TEXT NOT NULL,
    codigo_origem      BIGINT NOT NULL,
    origem_sistema     TEXT NOT NULL,
    razao_social       TEXT NOT NULL,
    nome_fantasia      TEXT,
    documento          TEXT NOT NULL,
    tipo_pessoa        TEXT NOT NULL CHECK (tipo_pessoa IN ('FISICA','JURIDICA')),
    inscricao_estadual TEXT,
    municipio          TEXT,
    uf                 CHAR(2),
    cep                TEXT,
    email              TEXT,
    telefone           TEXT,
    criado_em          TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_participante_origem UNIQUE (empresa_id, origem_sistema, codigo_origem)
);
CREATE INDEX IF NOT EXISTS ix_participante_atualizado_em
    ON erp.participante (atualizado_em);

-- sync.sync_outbox
CREATE TABLE IF NOT EXISTS sync.sync_outbox (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entidade        TEXT NOT NULL,
    registro_id     TEXT NOT NULL,
    operacao        TEXT NOT NULL CHECK (operacao IN ('UPSERT','DELETE')),
    tentativas      INT NOT NULL DEFAULT 0,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT now(),
    agendado_para   TIMESTAMPTZ NOT NULL DEFAULT now(),
    sincronizado_em TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_outbox_pendentes
    ON sync.sync_outbox (agendado_para) WHERE sincronizado_em IS NULL;

-- sync.watermark
CREATE TABLE IF NOT EXISTS sync.watermark (
    empresa_id     TEXT NOT NULL,
    entidade       TEXT NOT NULL,
    ultima_posicao TIMESTAMPTZ NOT NULL,
    atualizado_em  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (empresa_id, entidade)
);

-- migracao.erro
CREATE TABLE IF NOT EXISTS migracao.erro (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entidade    TEXT NOT NULL,
    registro_id TEXT NOT NULL,
    mensagem    TEXT NOT NULL,
    stack       TEXT,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_migracao_erro_entidade
    ON migracao.erro (entidade, criado_em);

-- migracao.job
CREATE TABLE IF NOT EXISTS migracao.job (
    id            UUID PRIMARY KEY,
    origem        TEXT NOT NULL,
    iniciado_em   TIMESTAMPTZ NOT NULL DEFAULT now(),
    finalizado_em TIMESTAMPTZ,
    sucesso       BOOLEAN,
    importados    INT NOT NULL DEFAULT 0,
    erros         INT NOT NULL DEFAULT 0,
    duracao_s     DOUBLE PRECISION NOT NULL DEFAULT 0
);
'''


# =====================================================================
#  EXECUÇÃO
# =====================================================================
def _aplicar(root: Path, grupo: str, force: bool, backup: bool, dry_run: bool) -> tuple[int, int, int]:
    criados = atualizados = pulados = 0
    for rel, content in GRUPO[grupo].items():
        dest = root / rel
        prefixo = {"model": "🧩", "impl": "⚙️ ", "ddl": "🗄️ "}[grupo]
        if not dest.exists():
            if dry_run:
                print(f"{prefixo} [NOVO]      {rel}")
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content, encoding="utf-8")
                print(f"{prefixo} [CRIADO]    {rel}")
            criados += 1
            continue
        if not force:
            print(f"{prefixo} [SKIP]      {rel}  (use --force)")
            pulados += 1
            continue
        if dry_run:
            print(f"{prefixo} [OVERWRITE] {rel}")
            atualizados += 1
            continue
        if backup:
            shutil.copy2(dest, dest.with_suffix(dest.suffix + ".bak"))
        dest.write_text(content, encoding="utf-8")
        print(f"{prefixo} [UPDATED]   {rel}")
        atualizados += 1
    return criados, atualizados, pulados


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--only", choices=["model", "impl", "ddl", "all"], default="all")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"❌ Raiz inválida: {root}", file=sys.stderr)
        return 1
    if not args.force and not args.dry_run:
        print("⚠️  Use --dry-run para revisar, ou --force --backup para aplicar.\n")
        return 2

    print(f"📁 Raiz: {root}\n🎯 Grupos: {args.only}\n")
    grupos = ["model", "impl", "ddl"] if args.only == "all" else [args.only]
    tot_c = tot_a = tot_p = 0
    for g in grupos:
        print(f"── {g.upper()} ──")
        c, a, p = _aplicar(root, g, args.force, args.backup, args.dry_run)
        tot_c += c; tot_a += a; tot_p += p
    print(f"\n📊 Criados: {tot_c}, Atualizados: {tot_a}, Pulados: {tot_p}")
    if args.dry_run:
        print("(dry-run — nada foi escrito)")
        return 0
    print("\nPróximos passos:")
    print("  psql -d erp_contabil -f ddl/schema.sql")
    print("  python -m compileall -q src tests && echo '✅'")
    print("  pytest -v && mypy src/ && ruff check src/")
    return 0


if __name__ == "__main__":
    sys.exit(main())