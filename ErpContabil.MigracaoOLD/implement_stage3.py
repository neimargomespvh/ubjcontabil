#!/usr/bin/env python3
"""implement_stage3.py — Pipeline completo (Empresa + Plano + SPED + Painel Web).

Uso:
    python implement_stage3.py --dry-run
    python implement_stage3.py --force --backup

Depois:
    pip install -r requirements-web.txt
    psql -d erp_contabil -f ddl/schema_stage3.sql   # ou python scripts/setup_db.py --ddl ddl/schema_stage3.sql
    ./scripts/run_admin.sh
    pytest -v && mypy src/ && ruff check src/
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

G: dict[str, dict[str, str]] = {
    "ddl": {}, "impl": {}, "load": {}, "infra": {},
    "web": {}, "scripts": {}, "tests": {}, "config": {},
}


# =====================================================================
#  DDL
# =====================================================================
G["ddl"]["ddl/schema_stage3.sql"] = r'''-- =========================================================
-- Stage 3 — tabelas erp.empresa, erp.conta_contabil, erp.sped_registro
-- Rodar:  psql -d erp_contabil -f ddl/schema_stage3.sql
-- =========================================================

CREATE TABLE IF NOT EXISTS erp.empresa (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id        TEXT NOT NULL,
    codigo_origem     BIGINT NOT NULL,
    origem_sistema    TEXT NOT NULL,
    razao_social      TEXT NOT NULL,
    cnpj              TEXT NOT NULL,
    uf                CHAR(2),
    regime_tributario TEXT,
    criado_em         TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_empresa_origem UNIQUE (empresa_id, origem_sistema, codigo_origem)
);

CREATE TABLE IF NOT EXISTS erp.conta_contabil (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id     TEXT NOT NULL,
    codigo         TEXT NOT NULL,
    nome           TEXT NOT NULL,
    codigo_pai     TEXT,
    natureza       TEXT NOT NULL CHECK (natureza IN ('SINTETICA','ANALITICA')),
    grau           INT  NOT NULL,
    natureza_saldo TEXT CHECK (natureza_saldo IN ('DEVEDORA','CREDORA')),
    criado_em      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_conta_empresa UNIQUE (empresa_id, codigo)
);
CREATE INDEX IF NOT EXISTS ix_conta_pai ON erp.conta_contabil (empresa_id, codigo_pai);

CREATE TABLE IF NOT EXISTS erp.sped_registro (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id   TEXT NOT NULL,
    arquivo      TEXT NOT NULL,
    numero_linha BIGINT NOT NULL,
    codigo       TEXT NOT NULL,
    campos_json  TEXT NOT NULL,
    linha_bruta  TEXT NOT NULL,
    criado_em    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_sped_registro UNIQUE (empresa_id, arquivo, numero_linha)
);
CREATE INDEX IF NOT EXISTS ix_sped_codigo ON erp.sped_registro (empresa_id, codigo);
'''


# =====================================================================
#  IMPL — extractors, transformers, infra
# =====================================================================
G["impl"]["src/domain/models/entities/sped_registro.py"] = r'''"""Registro genérico de um arquivo SPED."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SpedRegistro:
    """Linha do SPED já fatiada em (código do registro, campos).

    Attributes:
        codigo: código do registro SPED (ex.: "0150", "C100").
        campos: campos do registro, sem o pipe inicial/final.
        linha_bruta: linha original do arquivo (para logs de erro).
        arquivo: nome do arquivo de onde veio a linha.
        numero_linha: número da linha dentro do arquivo (1-based).
    """

    codigo: str
    campos: tuple[str, ...]
    linha_bruta: str
    arquivo: str = ""
    numero_linha: int = 0
'''


G["impl"]["src/extract/fortes/schema_discovery.py"] = r'''"""Descoberta do schema real da Fortes antes de mapear colunas."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.extract.fortes.connection import FortesConnectionFactory


@dataclass(frozen=True, slots=True)
class TabelaDescoberta:
    """Metadado de uma coluna descoberta no SQL Server da Fortes."""

    table_schema: str
    table_name: str
    column_name: str
    data_type: str
    is_nullable: str


class FortesSchemaDiscovery:
    """Lista tabelas e colunas da Fortes para confirmar o De-Para na UI."""

    _SQL = """
        SELECT t.TABLE_SCHEMA, t.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE, c.IS_NULLABLE
        FROM INFORMATION_SCHEMA.TABLES t WITH (NOLOCK)
        JOIN INFORMATION_SCHEMA.COLUMNS c WITH (NOLOCK)
          ON c.TABLE_SCHEMA = t.TABLE_SCHEMA AND c.TABLE_NAME = t.TABLE_NAME
        WHERE t.TABLE_TYPE = 'BASE TABLE'
        ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME, c.ORDINAL_POSITION
    """

    def __init__(self, factory: FortesConnectionFactory) -> None:
        self._factory = factory

    def descobrir(self) -> list[TabelaDescoberta]:
        with (
            self._factory.open() as conn,
            conn.cursor(as_dict=True) as cur,
        ):
            cur.execute(self._SQL)
            rows: list[dict[str, Any]] = cur.fetchall()
        return [
            TabelaDescoberta(
                table_schema=r["TABLE_SCHEMA"],
                table_name=r["TABLE_NAME"],
                column_name=r["COLUMN_NAME"],
                data_type=r["DATA_TYPE"],
                is_nullable=r["IS_NULLABLE"],
            )
            for r in rows
        ]
'''


G["impl"]["src/extract/fortes/empresa_extractor.py"] = r'''"""Extrator do cadastro de empresas da Fortes."""
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
                return int(row[0]) if row else None
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


G["impl"]["src/extract/fortes/plano_contas_extractor.py"] = r'''"""Extrator do plano de contas contábil da Fortes."""
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
                cur.execute("SELECT COUNT_BIG(*) FROM dbo.PLANO_CONTAS WITH (NOLOCK)")
                row = cur.fetchone()
                return int(row[0]) if row else None
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
            # Fortes às vezes usa "S"/"A" ou "01"/"02"
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


G["impl"]["src/extract/shared/file_chunk_reader.py"] = r'''"""Leitura de arquivos grandes em chunks de linhas."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path


class FileChunkReader:
    """Lê um arquivo de texto em lotes de N linhas."""

    def __init__(self, tamanho_chunk: int = 5_000, encoding: str = "utf-8") -> None:
        self._tamanho_chunk = tamanho_chunk
        self._encoding = encoding

    def ler(self, caminho: Path) -> Iterator[list[str]]:
        lote: list[str] = []
        with caminho.open(encoding=self._encoding, errors="replace") as f:
            for linha in f:
                lote.append(linha.rstrip("\r\n"))
                if len(lote) >= self._tamanho_chunk:
                    yield lote
                    lote = []
        if lote:
            yield lote
'''


G["impl"]["src/extract/tron/sped_txt_extractor.py"] = r'''"""Extrator de registros a partir de arquivos .txt do SPED Fiscal/Contribuições."""
from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path

from src.domain.contracts.extractor import IEntityExtractor
from src.domain.models.chunk import Chunk
from src.domain.models.entities.sped_registro import SpedRegistro
from src.transform.sped.parser import SpedLineParser


class SpedTxtExtractor(IEntityExtractor[SpedRegistro]):
    """Lê um arquivo SPED e emite apenas os registros de cadastro relevantes.

    Notes:
        O e-Fisco Ceará não expõe API pública de download. O caminho realista é
        o cliente baixar os .txt do SPED no portal da Receita/SEFAZ e subir
        no painel. Nunca faça scraping/automação de login no e-CAC sem
        procuração eletrônica válida.
    """

    REGISTROS_INTERESSE: frozenset[str] = frozenset(
        {"0000", "0150", "0190", "0200", "0500", "C100", "C170"}
    )

    def __init__(self, caminho: Path, tamanho_chunk: int = 5_000) -> None:
        self._caminho = caminho
        self._tamanho_chunk = tamanho_chunk

    def extract(
        self, stop_event: threading.Event | None = None
    ) -> Iterator[Chunk[SpedRegistro]]:
        lote: list[SpedRegistro] = []
        total = 0
        with self._caminho.open(encoding="utf-8", errors="replace") as f:
            for numero, linha in enumerate(f, start=1):
                if stop_event is not None and stop_event.is_set():
                    return
                registro = SpedLineParser.parse(linha)
                if registro is None:
                    continue
                if registro.codigo not in self.REGISTROS_INTERESSE:
                    continue
                # enriquece com contexto de arquivo/linha
                registro = SpedRegistro(
                    codigo=registro.codigo,
                    campos=registro.campos,
                    linha_bruta=registro.linha_bruta,
                    arquivo=self._caminho.name,
                    numero_linha=numero,
                )
                lote.append(registro)
                total += 1
                if len(lote) >= self._tamanho_chunk:
                    yield Chunk(itens=lote, total_acumulado=total)
                    lote = []
        if lote:
            yield Chunk(itens=lote, total_acumulado=total)
'''


G["impl"]["src/extract/tron/firebird_extractor.py"] = r'''"""Extrator da base Firebird da Tron Informática.

Notes:
    O schema da Tron varia bastante por versão. Esta classe é um esqueleto
    funcional que conecta, descobre tabelas e permite queries ad-hoc. O
    mapeamento das colunas deve ser confirmado contra a base real do cliente.
"""
from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from src.domain.models.chunk import Chunk


@dataclass(frozen=True, slots=True)
class TronConnectionOptions:
    """Credenciais do Firebird da Tron.

    Ordem dos campos: obrigatórios primeiro, opcionais (com default) depois.
    """

    host: str
    database: str
    usuario: str
    senha: str
    porta: int = 3050
    charset: str = "UTF8"


class TronFirebirdExtractor:
    """Extrai registros da Tron via Firebird."""

    def __init__(
        self, opt: TronConnectionOptions, tamanho_chunk: int = 5_000
    ) -> None:
        self._opt = opt
        self._tamanho_chunk = tamanho_chunk

    @contextmanager
    def _conectar(self) -> Iterator[Any]:
        from firebird.driver import connect  # import tardio

        dsn = f"{self._opt.host}/{self._opt.porta}:{self._opt.database}"
        conn = connect(
            dsn,
            user=self._opt.usuario,
            password=self._opt.senha,
            charset=self._opt.charset,
        )
        try:
            yield conn
        finally:
            conn.close()

    def listar_tabelas(self) -> list[str]:
        """Retorna nomes de tabelas do schema do cliente (útil para De-Para)."""
        with self._conectar() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT TRIM(RDB$RELATION_NAME) FROM RDB$RELATIONS "
                "WHERE RDB$SYSTEM_FLAG = 0 ORDER BY 1"
            )
            return [str(r[0]).strip() for r in cur.fetchall()]

    def extract_participantes(
        self, stop_event: threading.Event | None = None
    ) -> Iterator[Chunk[object]]:
        """Esqueleto: consulta ad-hoc até o De-Para real ser confirmado.

        Notes:
            Sem o schema real do cliente, esta função não pode mapear colunas.
            Use `listar_tabelas()` primeiro e depois implemente a query.
        """
        raise NotImplementedError(
            "TODO: confirmar schema da Tron no cliente piloto antes de implementar"
        )
        yield  # pragma: no cover
'''


G["impl"]["src/transform/sped/parser.py"] = r'''"""Parser de linhas do SPED."""
from __future__ import annotations

from src.domain.models.entities.sped_registro import SpedRegistro


class SpedLineParser:
    """Converte uma linha bruta do SPED em SpedRegistro.

    Formato: |REG|campo1|campo2|...|
    """

    @staticmethod
    def parse(linha: str) -> SpedRegistro | None:
        """Retorna None se a linha for inválida (vazia, sem pipes, curta)."""
        if not linha or not linha.startswith("|"):
            return None
        limpa = linha.rstrip("\r\n")
        partes = limpa.split("|")
        if len(partes) < 3:
            return None
        codigo = partes[1]
        if not codigo:
            return None
        # partes[0] é vazio, partes[1] é o código, partes[-1] é vazio
        campos = tuple(partes[2:-1])
        return SpedRegistro(codigo=codigo, campos=campos, linha_bruta=limpa)
'''


G["impl"]["src/transform/sped/block_reader.py"] = r'''"""Leitor de blocos do SPED (0000, 0150, C100...)."""
from __future__ import annotations

from collections.abc import Iterable, Iterator

from src.domain.models.entities.sped_registro import SpedRegistro


class SpedBlockReader:
    """Filtra registros do SPED por bloco (prefixo do código)."""

    def __init__(self, registros: Iterable[SpedRegistro]) -> None:
        self._registros = registros

    def por_bloco(self, bloco: str) -> Iterator[SpedRegistro]:
        """Retorna apenas registros cujo código começa pelo bloco (ex.: 'C')."""
        for r in self._registros:
            if r.codigo.startswith(bloco):
                yield r
'''


G["impl"]["src/transform/mappings/sped_para_erp_map.py"] = r'''"""Dicionário De-Para SPED → ERP."""
from __future__ import annotations


class SpedParaErpMap:
    """Mapeamento de campos dos registros SPED para o schema do ERP.

    Notes:
        Os índices referem-se à posição do campo no registro SPED
        (0 = primeiro campo após o código), conforme Guia Prático SPED Fiscal.
    """

    # 0150 — Participantes: COD_PART, NOME, COD_PAIS, CNPJ, CPF, IE, COD_MUN, ...
    R0150: dict[int, str] = {
        0: "codigo_origem",
        1: "razao_social",
        3: "documento_cnpj",
        4: "documento_cpf",
        5: "inscricao_estadual",
        6: "municipio",
    }

    # 0500 — Plano de contas: DT_ALT, COD_NAT_CC, IND_CTA, NIVEL, COD_CTA, NOME_CTA
    R0500: dict[int, str] = {
        1: "natureza",     # 01=Sintética, 02=Analítica
        3: "grau",         # nível
        4: "codigo",
        5: "nome",
    }
'''


G["impl"]["src/infrastructure/resilience/retry_policy.py"] = r'''"""Política de retry com backoff exponencial."""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class RetryPolicy:
    """Executa uma função com tentativas e backoff exponencial."""

    def __init__(
        self,
        tentativas: int = 5,
        backoff_inicial_s: float = 1.0,
        fator: float = 2.0,
        max_backoff_s: float = 60.0,
    ) -> None:
        if tentativas < 1:
            raise ValueError("tentativas deve ser >= 1")
        self._tentativas = tentativas
        self._backoff_inicial_s = backoff_inicial_s
        self._fator = fator
        self._max_backoff_s = max_backoff_s

    def executar(self, fn: Callable[[], T]) -> T:
        """Executa `fn`; em caso de exceção, espera e tenta de novo."""
        ultimo: BaseException | None = None
        for tentativa in range(self._tentativas):
            try:
                return fn()
            except Exception as e:
                ultimo = e
                if tentativa == self._tentativas - 1:
                    break
                espera = min(
                    self._max_backoff_s,
                    self._backoff_inicial_s * (self._fator ** tentativa),
                )
                time.sleep(espera)
        assert ultimo is not None
        raise ultimo
'''


G["impl"]["src/infrastructure/telemetry/metrics.py"] = r'''"""Métricas de execução do migrador."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class MigrationMetrics:
    """Contadores simples expostos ao painel Admin."""

    registros_lidos: int = 0
    registros_validos: int = 0
    registros_rejeitados: int = 0
    bytes_lidos: int = 0
    duracao_por_chunk_s: list[float] = field(default_factory=list)

    def registrar_chunk(self, lidos: int, validos: int, duracao_s: float) -> None:
        self.registros_lidos += lidos
        self.registros_validos += validos
        self.registros_rejeitados += lidos - validos
        self.duracao_por_chunk_s.append(duracao_s)

    @property
    def duracao_total_s(self) -> float:
        return sum(self.duracao_por_chunk_s)
'''


G["impl"]["src/infrastructure/job_registry.py"] = r'''"""Registro em memória de jobs de migração (para o painel Admin)."""
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
'''


# =====================================================================
#  LOAD — loaders estendidos para 4 entidades
# =====================================================================
G["load"]["src/load/postgres_bulk_loader.py"] = r'''"""Bulk Insert no PostgreSQL via COPY ... FROM STDIN (FORMAT BINARY)."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from psycopg import sql

from src.domain.models.entities.conta_contabil import ContaContabil
from src.domain.models.entities.empresa import EmpresaOrigem
from src.domain.models.entities.participante import ParticipanteDestino
from src.domain.models.entities.sped_registro import SpedRegistro

if TYPE_CHECKING:
    from psycopg import Connection


def _copy_sql(tabela: str, colunas: list[str]) -> sql.Composed:
    return sql.SQL("COPY {t} ({c}) FROM STDIN (FORMAT BINARY)").format(
        t=sql.Identifier("erp", tabela),
        c=sql.SQL(", ").join(sql.Identifier(c) for c in colunas),
    )


_COPY_PARTICIPANTE = _copy_sql("participante", [
    "empresa_id", "codigo_origem", "origem_sistema", "razao_social",
    "nome_fantasia", "documento", "tipo_pessoa", "inscricao_estadual",
    "municipio", "uf", "cep", "email", "telefone",
])
_TIPOS_PARTICIPANTE = ["text", "int8", "text", "text", "text", "text", "text",
                       "text", "text", "text", "text", "text", "text"]

_COPY_EMPRESA = _copy_sql("empresa", [
    "empresa_id", "codigo_origem", "origem_sistema", "razao_social",
    "cnpj", "uf", "regime_tributario",
])
_TIPOS_EMPRESA = ["text", "int8", "text", "text", "text", "text", "text"]

_COPY_CONTA = _copy_sql("conta_contabil", [
    "empresa_id", "codigo", "nome", "codigo_pai", "natureza",
    "grau", "natureza_saldo",
])
_TIPOS_CONTA = ["text", "text", "text", "text", "text", "int4", "text"]

_COPY_SPED = _copy_sql("sped_registro", [
    "empresa_id", "arquivo", "numero_linha", "codigo", "campos_json", "linha_bruta",
])
_TIPOS_SPED = ["text", "text", "int8", "text", "text", "text"]


class PostgresBinaryBulkLoader:
    """Insere grandes volumes via COPY BINARY (3–10× mais rápido que INSERT)."""

    def __init__(self, connection_string: str) -> None:
        self._connection_string = connection_string

    # -- participantes ------------------------------------------------
    def inserir_participantes(
        self,
        conn: Connection,
        tx: object | None,
        empresa_id: str,
        itens: list[ParticipanteDestino],
    ) -> int:
        with conn.cursor() as cur, cur.copy(_COPY_PARTICIPANTE) as copy:
            copy.set_types(_TIPOS_PARTICIPANTE)
            for p in itens:
                copy.write_row((
                    empresa_id, p.codigo_origem, p.origem_sistema, p.razao_social,
                    p.nome_fantasia, p.documento, p.tipo_pessoa,
                    p.inscricao_estadual, p.municipio, p.uf, p.cep, p.email, p.telefone,
                ))
        return len(itens)

    # -- empresas -----------------------------------------------------
    def inserir_empresas(
        self,
        conn: Connection,
        empresa_id: str,
        itens: list[EmpresaOrigem],
    ) -> int:
        with conn.cursor() as cur, cur.copy(_COPY_EMPRESA) as copy:
            copy.set_types(_TIPOS_EMPRESA)
            for e in itens:
                copy.write_row((
                    empresa_id, e.codigo_origem, "FORTES",
                    e.razao_social or "(sem razão social)",
                    (e.cnpj or "").strip(), e.uf, e.regime_tributario,
                ))
        return len(itens)

    # -- contas contábeis --------------------------------------------
    def inserir_contas(
        self,
        conn: Connection,
        empresa_id: str,
        itens: list[ContaContabil],
    ) -> int:
        with conn.cursor() as cur, cur.copy(_COPY_CONTA) as copy:
            copy.set_types(_TIPOS_CONTA)
            for c in itens:
                copy.write_row((
                    empresa_id, c.codigo, c.nome, c.codigo_pai,
                    c.natureza, c.grau, c.natureza_saldo,
                ))
        return len(itens)

    # -- SPED (auditoria) --------------------------------------------
    def inserir_sped(
        self,
        conn: Connection,
        empresa_id: str,
        itens: list[SpedRegistro],
    ) -> int:
        with conn.cursor() as cur, cur.copy(_COPY_SPED) as copy:
            copy.set_types(_TIPOS_SPED)
            for r in itens:
                copy.write_row((
                    empresa_id, r.arquivo, r.numero_linha, r.codigo,
                    json.dumps(list(r.campos), ensure_ascii=False),
                    r.linha_bruta,
                ))
        return len(itens)
'''


G["load"]["src/load/postgres_fallback_loader.py"] = r'''"""Fallback linha-a-linha com SAVEPOINT para o caso de COPY falhar."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

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

    # -- interno ------------------------------------------------------
    def _inserir(
        self,
        conn: Connection,
        sql: str,
        entidade: str,
        rows: list[tuple],
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


# =====================================================================
#  INFRA — orquestrador refatorado
# =====================================================================
G["infra"]["src/infrastructure/orchestrator.py"] = r'''"""Orquestrador: pipeline genérico (Empresa + Plano + Participante + SPED)."""
from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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


@dataclass(slots=True)
class _Etapa:
    nome: str
    entidade: str
    extractor: Any
    transformer: Any | None
    loader: Callable[[psycopg.Connection, str, list[Any]], int]
    fallback: Callable[[psycopg.Connection, str, list[Any]], int]


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

    # -- público ------------------------------------------------------
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
        job_id = str(uuid.uuid4())
        empresa_id = opt.empresa_id or opt.database
        result = MigrationResult(job_id=job_id, empresa_id=empresa_id)
        inicio = time.time()
        self._logger.iniciar_job(job_id, "FORTES")
        progresso(MigrationProgress(etapa_atual="Conectando à Fortes…"))

        factory = FortesConnectionFactory(opt)
        configs = self._configurar_etapas_fortes(factory, opt, etapas)

        try:
            with psycopg.connect(self._conninfo) as erp_conn:
                for etapa in configs:
                    self._executar_etapa(
                        erp_conn, empresa_id, etapa, result, progresso
                    )
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
        job_id = str(uuid.uuid4())
        result = MigrationResult(job_id=job_id, empresa_id=empresa_id)
        inicio = time.time()
        self._logger.iniciar_job(job_id, "SPED")
        progresso(MigrationProgress(etapa_atual="Lendo arquivos SPED…"))

        try:
            with psycopg.connect(self._conninfo) as erp_conn:
                for caminho in caminhos:
                    etapa = _Etapa(
                        nome=f"sped:{Path(caminho).name}",
                        entidade="SPED",
                        extractor=SpedTxtExtractor(Path(caminho)),
                        transformer=None,
                        loader=lambda c, eid, itens: self._bulk.inserir_sped(c, eid, itens),
                        fallback=lambda c, eid, itens: self._fallback.inserir_sped(c, eid, itens),
                    )
                    self._executar_etapa(erp_conn, empresa_id, etapa, result, progresso)
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

    # -- config -------------------------------------------------------
    def _configurar_etapas_fortes(
        self,
        factory: FortesConnectionFactory,
        opt: FortesConnectionOptions,
        etapas: Sequence[str],
    ) -> list[_Etapa]:
        resultado: list[_Etapa] = []
        for nome in etapas:
            if nome == "empresa":
                resultado.append(_Etapa(
                    nome="empresa", entidade="EMPRESA",
                    extractor=FortesEmpresaExtractor(factory, opt.tamanho_chunk),
                    transformer=None,
                    loader=lambda c, eid, itens: self._bulk.inserir_empresas(c, eid, itens),
                    fallback=lambda c, eid, itens: self._fallback.inserir_empresas(c, eid, itens),
                ))
            elif nome == "plano_contas":
                resultado.append(_Etapa(
                    nome="plano_contas", entidade="CONTA_CONTABIL",
                    extractor=FortesPlanoContasExtractor(factory, opt.tamanho_chunk),
                    transformer=None,
                    loader=lambda c, eid, itens: self._bulk.inserir_contas(c, eid, itens),
                    fallback=lambda c, eid, itens: self._fallback.inserir_contas(c, eid, itens),
                ))
            elif nome == "participante":
                resultado.append(_Etapa(
                    nome="participante", entidade="PARTICIPANTE",
                    extractor=FortesParticipanteExtractor(factory, opt.tamanho_chunk),
                    transformer=self._transformer,
                    loader=lambda c, eid, itens: self._bulk.inserir_participantes(c, None, eid, itens),
                    fallback=lambda c, eid, itens: self._fallback.inserir_participantes(c, None, eid, itens),
                ))
            else:
                raise ValueError(f"Etapa desconhecida: {nome}")
        return resultado

    # -- pipeline genérico -------------------------------------------
    def _executar_etapa(
        self,
        erp_conn: psycopg.Connection,
        empresa_id: str,
        etapa: _Etapa,
        result: MigrationResult,
        progresso: Callable[[MigrationProgress], None],
    ) -> None:
        extractor = etapa.extractor
        total_hint: int | None = None
        if callable(getattr(extractor, "count_estimado", None)):
            try:
                total_hint = extractor.count_estimado()
            except Exception:
                total_hint = None

        for chunk in self._iterar(extractor):
            validos: list[Any] = []
            if etapa.transformer is not None:
                for item in chunk.itens:
                    t = etapa.transformer.transform(item)
                    if t.sucesso and t.valor is not None:
                        validos.append(t.valor)
                    else:
                        result.erros += 1
                        rid = getattr(item, "codigo_origem", "?")
                        self._logger.erro(etapa.entidade, str(rid), t.motivo or "?")
            else:
                validos = list(chunk.itens)

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
                    self._outbox.enfileirar(
                        erp_conn, None, etapa.entidade, empresa_id, OperacaoSync.UPSERT
                    )
                    result.importados += n

            pct = 0.0
            if total_hint:
                pct = min(99.0, 100.0 * chunk.total_acumulado / total_hint)
            progresso(MigrationProgress(
                etapa_atual=f"Importando {etapa.nome}…",
                registros_processados=chunk.total_acumulado,
                registros_com_erro=result.erros,
                percentual=pct,
            ))

    @staticmethod
    def _iterar(extractor: Any) -> Iterable[Any]:
        return extractor.extract()  # type: ignore[no-any-return]
'''


# =====================================================================
#  WEB
# =====================================================================
G["web"]["src/web/schemas.py"] = r'''"""Modelos Pydantic para a API do painel Admin."""
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
    etapas: list[str] = Field(default_factory=lambda: ["empresa", "plano_contas", "participante"])
    tamanho_chunk: int = 5_000


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
'''


G["web"]["src/web/app.py"] = r'''"""Painel Admin — Utilitários de Migração (FastAPI).

Rodar com:
    uvicorn src.web.app:app --reload --port 8000
Acessar:
    http://localhost:8000/admin/utilitarios/migracao
"""
from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, UploadFile
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
from src.web.schemas import (
    ArquivoUploadResponse,
    FortesIniciarRequest,
    FortesTestarRequest,
    JobResponse,
    StatusResponse,
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


# -- páginas ---------------------------------------------------------
@app.get("/admin/utilitarios/migracao", response_class=HTMLResponse)
def pagina_migracao(request: Request) -> HTMLResponse:
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


# -- Fortes ---------------------------------------------------------
@app.post("/api/migracao/fortes/testar")
def testar_fortes(req: FortesTestarRequest) -> dict[str, bool]:
    orc = _get_orc()
    ok = orc.testar_conexao_fortes(_to_options(req))
    return {"ok": ok}


@app.post("/api/migracao/fortes/iniciar", response_model=JobResponse)
def iniciar_fortes(req: FortesIniciarRequest) -> JobResponse:
    orc = _get_orc()
    job_id = str(uuid.uuid4())
    _registry.criar(job_id, "FORTES", f"Fortes → {req.database}")

    opt = _to_options(req)
    opt.tamanho_chunk = req.tamanho_chunk

    def _run() -> None:
        try:
            result = orc.executar_migracao_fortes(
                opt,
                lambda p: _registry.atualizar_progresso(job_id, p),
                etapas=tuple(req.etapas),
            )
            _registry.finalizar(job_id, result)
        except Exception as e:
            _registry.falhar(job_id, str(e))

    _executor.submit(_run)
    return JobResponse(job_id=job_id, status="EM_ANDAMENTO",
                       descricao=f"Fortes → {req.database}")


# -- Arquivos (SPED/NF-e) -------------------------------------------
@app.post("/api/migracao/arquivos/upload", response_model=ArquivoUploadResponse)
async def upload_arquivos(
    empresa_id: str, arquivos: list[UploadFile]
) -> ArquivoUploadResponse:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    salvos: list[str] = []
    for f in arquivos:
        if f.filename is None:
            continue
        if not (f.filename.endswith(".txt") or f.filename.endswith(".xml")):
            continue
        destino = UPLOAD_DIR / f"{uuid.uuid4().hex}_{f.filename}"
        destino.write_bytes(await f.read())
        salvos.append(str(destino))
    return ArquivoUploadResponse(arquivos=salvos, empresa_id=empresa_id)


@app.post("/api/migracao/arquivos/iniciar", response_model=JobResponse)
def iniciar_arquivos(
    empresa_id: str, caminhos: list[str]
) -> JobResponse:
    orc = _get_orc()
    if not caminhos:
        raise HTTPException(400, "Nenhum arquivo informado")
    job_id = str(uuid.uuid4())
    _registry.criar(job_id, "SPED", f"{len(caminhos)} arquivo(s)")

    def _run() -> None:
        try:
            result = orc.executar_migracao_arquivos(
                caminhos, empresa_id,
                lambda p: _registry.atualizar_progresso(job_id, p),
            )
            _registry.finalizar(job_id, result)
        except Exception as e:
            _registry.falhar(job_id, str(e))

    _executor.submit(_run)
    return JobResponse(job_id=job_id, status="EM_ANDAMENTO",
                       descricao=f"{len(caminhos)} arquivo(s)")


# -- status ----------------------------------------------------------
@app.get("/api/migracao/status/{job_id}", response_model=StatusResponse)
def status(job_id: str) -> StatusResponse:
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


@app.get("/api/migracao/jobs")
def listar_jobs() -> JSONResponse:
    return JSONResponse([
        {
            "job_id": s.job_id, "tipo": s.tipo, "status": s.status.value,
            "iniciado_em": s.iniciado_em.isoformat(),
            "descricao": s.descricao,
        }
        for s in _registry.listar()
    ])


# -- helpers ---------------------------------------------------------
def _to_options(req: FortesTestarRequest) -> FortesConnectionOptions:
    return FortesConnectionOptions(
        host=req.host, porta=req.porta, database=req.database,
        usuario=req.usuario, senha=req.senha, empresa_id=req.empresa_id,
    )
'''


G["web"]["src/web/templates/utilitarios_migracao.html"] = r'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Migração — Admin</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <header>
    <h1>Utilitários do Admin — Migração de Dados</h1>
    <span id="health" class="badge">verificando…</span>
  </header>

  <section class="card">
    <h2>1) Migrador Fortes Tecnologia (SQL Server)</h2>
    <form id="fortes-form">
      <div class="grid">
        <label>Host        <input name="host" value="localhost" required></label>
        <label>Porta       <input name="porta" type="number" value="1433" required></label>
        <label>Database    <input name="database" required></label>
        <label>Usuário     <input name="usuario" required></label>
        <label>Senha       <input name="senha" type="password" required></label>
        <label>Empresa ID  <input name="empresa_id" required></label>
      </div>
      <fieldset>
        <legend>Etapas</legend>
        <label><input type="checkbox" name="etapas" value="empresa" checked> Empresa</label>
        <label><input type="checkbox" name="etapas" value="plano_contas" checked> Plano de contas</label>
        <label><input type="checkbox" name="etapas" value="participante" checked> Participantes</label>
      </fieldset>
      <div class="actions">
        <button type="button" id="fortes-test">Testar conexão</button>
        <button type="submit">Iniciar migração</button>
      </div>
    </form>
  </section>

  <section class="card">
    <h2>2) Migrador Tron / SEFAZ-CE (SPED .txt / NF-e .xml)</h2>
    <div id="dropzone" class="dropzone">
      Arraste arquivos .txt (SPED) ou .xml (NF-e) aqui, ou
      <input type="file" id="arquivo-input" multiple accept=".txt,.xml">
    </div>
    <label>Empresa ID <input id="empresa-id-arq" required></label>
    <ul id="lista-arquivos"></ul>
    <div class="actions">
      <button id="arq-iniciar" disabled>Processar arquivos</button>
    </div>
  </section>

  <section class="card" id="progresso-card" hidden>
    <h2>Progresso — <span id="job-id"></span></h2>
    <div class="progress">
      <div id="progress-bar" class="progress-bar" style="width:0%">0%</div>
    </div>
    <p id="etapa"></p>
    <p>
      <strong>Processados:</strong> <span id="processados">0</span> ·
      <strong>Erros:</strong> <span id="erros">0</span> ·
      <strong>Importados:</strong> <span id="importados">0</span>
    </p>
    <p id="erro" class="erro"></p>
  </section>

  <script src="/static/app.js"></script>
</body>
</html>
'''


G["web"]["src/web/static/app.js"] = r'''/* Painel Admin — polling de jobs e upload de arquivos. */
(() => {
  const $ = (sel) => document.querySelector(sel);
  const fmt = (n) => n.toLocaleString("pt-BR");
  let uploads = [];

  async function health() {
    try {
      const r = await fetch("/api/migracao/health");
      const d = await r.json();
      const el = $("#health");
      el.textContent = d.status === "ok" ? "🟢 DB OK" : "🔴 " + (d.detalhe || "erro");
      el.className = "badge " + (d.status === "ok" ? "ok" : "bad");
    } catch {
      $("#health").textContent = "🔴 API offline";
    }
  }

  async function testarFortes() {
    const form = $("#fortes-form");
    const data = Object.fromEntries(new FormData(form).entries());
    data.porta = parseInt(data.porta, 10);
    ["etapas"].forEach((k) => delete data[k]);
    try {
      const r = await fetch("/api/migracao/fortes/testar", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      const d = await r.json();
      alert(d.ok ? "✅ Conexão OK" : "❌ Falha na conexão (ver migracao_erros.log)");
    } catch (e) { alert("Erro: " + e); }
  }

  async function iniciarFortes(e) {
    e.preventDefault();
    const form = $("#fortes-form");
    const data = Object.fromEntries(new FormData(form).entries());
    data.porta = parseInt(data.porta, 10);
    data.etapas = [...form.querySelectorAll("input[name=etapas]:checked")]
      .map((i) => i.value);
    if (data.etapas.length === 0) { alert("Selecione ao menos uma etapa"); return; }
    const r = await fetch("/api/migracao/fortes/iniciar", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!r.ok) { alert("Erro: " + (await r.text())); return; }
    const d = await r.json();
    acompanhar(d.job_id);
  }

  function renderUploads() {
    const ul = $("#lista-arquivos");
    ul.innerHTML = "";
    uploads.forEach((u) => {
      const li = document.createElement("li");
      li.textContent = u.nome;
      ul.appendChild(li);
    });
    $("#arq-iniciar").disabled = uploads.length === 0;
  }

  async function enviarArquivos(files) {
    const empresaId = $("#empresa-id-arq").value.trim();
    if (!empresaId) { alert("Preencha Empresa ID antes de enviar"); return; }
    const fd = new FormData();
    for (const f of files) fd.append("arquivos", f);
    const r = await fetch(
      `/api/migracao/arquivos/upload?empresa_id=${encodeURIComponent(empresaId)}`,
      { method: "POST", body: fd },
    );
    if (!r.ok) { alert("Erro no upload: " + (await r.text())); return; }
    const d = await r.json();
    d.arquivos.forEach((p, i) => uploads.push({ caminho: p, nome: files[i].name }));
    renderUploads();
  }

  async function iniciarArquivos() {
    const empresaId = $("#empresa-id-arq").value.trim();
    const caminhos = uploads.map((u) => u.caminho);
    const r = await fetch(
      `/api/migracao/arquivos/iniciar?empresa_id=${encodeURIComponent(empresaId)}`,
      {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(caminhos),
      },
    );
    if (!r.ok) { alert("Erro: " + (await r.text())); return; }
    const d = await r.json();
    acompanhar(d.job_id);
  }

  function acompanhar(jobId) {
    $("#progresso-card").hidden = false;
    $("#job-id").textContent = jobId.slice(0, 8);
    const iv = setInterval(async () => {
      const r = await fetch(`/api/migracao/status/${jobId}`);
      if (!r.ok) { clearInterval(iv); return; }
      const d = await r.json();
      $("#progress-bar").style.width = d.percentual.toFixed(1) + "%";
      $("#progress-bar").textContent = d.percentual.toFixed(1) + "%";
      $("#etapa").textContent = d.etapa_atual || "—";
      $("#processados").textContent = fmt(d.registros_processados);
      $("#erros").textContent = fmt(d.registros_com_erro);
      $("#importados").textContent = fmt(d.importados);
      $("#erro").textContent = d.erro || "";
      if (["CONCLUIDO", "FALHOU", "CANCELADO"].includes(d.status)) {
        clearInterval(iv);
        $("#etapa").textContent = d.status === "CONCLUIDO" ? "✅ Concluído" : "❌ " + (d.erro || "falhou");
      }
    }, 1000);
  }

  // -- bindings
  $("#fortes-test").addEventListener("click", testarFortes);
  $("#fortes-form").addEventListener("submit", iniciarFortes);
  $("#arq-iniciar").addEventListener("click", iniciarArquivos);
  $("#arquivo-input").addEventListener("change", (e) => enviarArquivos(e.target.files));
  $("#dropzone").addEventListener("dragover", (e) => e.preventDefault());
  $("#dropzone").addEventListener("drop", (e) => {
    e.preventDefault();
    if (e.dataTransfer?.files?.length) enviarArquivos(e.dataTransfer.files);
  });

  health();
  setInterval(health, 30_000);
})();
'''


G["web"]["src/web/static/style.css"] = r'''* { box-sizing: border-box; }
body { font-family: system-ui, sans-serif; margin: 0; background: #f4f5f7; color: #222; }
header { background: #1e293b; color: #fff; padding: 1rem 2rem; display: flex;
         align-items: center; justify-content: space-between; }
header h1 { margin: 0; font-size: 1.25rem; }
.badge { padding: 0.25rem 0.6rem; border-radius: 4px; font-size: 0.8rem; }
.badge.ok  { background: #16a34a; }
.badge.bad { background: #dc2626; }
.card { background: #fff; margin: 1rem 2rem; padding: 1rem 1.5rem;
        border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.card h2 { margin-top: 0; font-size: 1rem; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px,1fr));
        gap: 0.75rem; margin-bottom: 1rem; }
.grid label { display: flex; flex-direction: column; font-size: 0.85rem; }
.grid input { padding: 0.4rem; border: 1px solid #cbd5e1; border-radius: 4px; }
fieldset { border: 1px dashed #cbd5e1; border-radius: 4px; margin: 0 0 1rem;
           padding: 0.5rem 1rem; }
fieldset label { margin-right: 1rem; }
.actions { display: flex; gap: 0.5rem; margin-top: 1rem; }
button { padding: 0.5rem 1rem; border: none; border-radius: 4px;
         background: #2563eb; color: #fff; cursor: pointer; font-weight: 500; }
button:disabled { background: #94a3b8; cursor: not-allowed; }
button[type=button] { background: #64748b; }
.dropzone { border: 2px dashed #94a3b8; padding: 2rem; text-align: center;
            border-radius: 8px; margin-bottom: 1rem; }
.dropzone input[type=file] { display: block; margin: 0.5rem auto 0; }
.progress { height: 24px; background: #e2e8f0; border-radius: 4px;
            overflow: hidden; margin: 0.5rem 0; }
.progress-bar { background: #2563eb; color: #fff; text-align: center;
                line-height: 24px; transition: width 0.3s; }
.erro { color: #dc2626; font-family: monospace; font-size: 0.85rem; }
'''


# =====================================================================
#  SCRIPTS
# =====================================================================
G["scripts"]["scripts/demo_fortes.py"] = r'''#!/usr/bin/env python3
"""Demo: executa a migração Fortes sem o painel web (CLI)."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

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
        "ERP_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/erp_contabil"))
    args = p.parse_args()

    opt = FortesConnectionOptions(
        host=args.host, porta=args.porta, database=args.database,
        usuario=args.usuario, senha=args.senha, empresa_id=args.empresa_id,
    )
    logger = MigrationLogger(Path("migracao_erros.log"), args.conninfo)
    orc = MigrationOrchestrator(
        conninfo=args.conninfo,
        logger=logger,
        bulk_loader=PostgresBinaryBulkLoader(args.conninfo),
        fallback_loader=PostgresFallbackRowLoader(logger),
        outbox=SyncOutboxWriter(),
        transformer=ParticipanteTransformer(),
    )

    print(f"🔌 Testando conexão {args.host}:{args.porta}/{args.database}…")
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
"""Demo: importa um arquivo .txt do SPED."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

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
        "ERP_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/erp_contabil"))
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


G["scripts"]["scripts/run_admin.sh"] = r'''#!/usr/bin/env bash
# Sobe o painel Admin com uvicorn.
set -euo pipefail
cd "$(dirname "$0")/.."
exec uvicorn src.web.app:app --host 0.0.0.0 --port "${PORT:-8000}" --reload
'''


# =====================================================================
#  TESTS
# =====================================================================
G["tests"]["tests/test_sped_parser.py"] = r'''"""Testes do parser de linhas SPED."""
from __future__ import annotations

import pytest

from src.transform.sped.parser import SpedLineParser


def test_parse_0150_valido() -> None:
    linha = "|0150|PART001|Fornecedor XYZ|1058|11222333000181||123456789|3550308|||Rua A|100|||"
    r = SpedLineParser.parse(linha)
    assert r is not None
    assert r.codigo == "0150"
    assert r.campos[0] == "PART001"
    assert r.campos[1] == "Fornecedor XYZ"


@pytest.mark.parametrize("invalida", ["", "0150|sem|pipe-inicial", "||"])
def test_parse_invalida(invalida: str) -> None:
    assert SpedLineParser.parse(invalida) is None


def test_parse_0000_valido() -> None:
    linha = "|0000|017|0|01012024|31122024|EMPRESA LTDA|12345678000199|CE|123456789||3550308|||A|1|"
    r = SpedLineParser.parse(linha)
    assert r is not None
    assert r.codigo == "0000"
    assert "EMPRESA LTDA" in r.campos
'''


G["tests"]["tests/test_retry_policy.py"] = r'''"""Testes da política de retry."""
from __future__ import annotations

import pytest

from src.infrastructure.resilience.retry_policy import RetryPolicy


def test_retry_sucesso_imediato() -> None:
    chamadas = {"n": 0}

    def fn() -> str:
        chamadas["n"] += 1
        return "ok"

    policy = RetryPolicy(tentativas=3, backoff_inicial_s=0.01)
    assert policy.executar(fn) == "ok"
    assert chamadas["n"] == 1


def test_retry_recupera_apos_falhas() -> None:
    chamadas = {"n": 0}

    def fn() -> str:
        chamadas["n"] += 1
        if chamadas["n"] < 3:
            raise RuntimeError("flaky")
        return "ok"

    policy = RetryPolicy(tentativas=5, backoff_inicial_s=0.01)
    assert policy.executar(fn) == "ok"
    assert chamadas["n"] == 3


def test_retry_esgota() -> None:
    policy = RetryPolicy(tentativas=3, backoff_inicial_s=0.01)

    def sempre_falha() -> str:
        raise RuntimeError("sempre")

    with pytest.raises(RuntimeError, match="sempre"):
        policy.executar(sempre_falha)
'''


G["tests"]["tests/test_integration.py"] = r'''"""Testes de integração — exigem PostgreSQL real.

Skip automático se `ERP_TEST_DATABASE_URL` não estiver setado ou se a
conexão falhar. Rodar com:
    ERP_TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/erp_contabil_test" \\
        pytest -m integration -v
"""
from __future__ import annotations

import os
import uuid

import pytest

psycopg = pytest.importorskip("psycopg")

pytestmark = pytest.mark.integration


def _conninfo() -> str:
    return os.environ.get("ERP_TEST_DATABASE_URL", "")


@pytest.fixture(scope="module")
def db_ok() -> bool:
    if not _conninfo():
        pytest.skip("ERP_TEST_DATABASE_URL não setado")
    try:
        with psycopg.connect(_conninfo(), connect_timeout=2):
            return True
    except Exception:
        pytest.skip("PostgreSQL não disponível")


def test_bulk_loader_participantes(db_ok: bool) -> None:
    from src.domain.models.entities.participante import ParticipanteDestino
    from src.load.postgres_bulk_loader import PostgresBinaryBulkLoader

    if not db_ok:
        return
    empresa_id = f"test-{uuid.uuid4().hex[:8]}"
    itens = [
        ParticipanteDestino(
            codigo_origem=i, razao_social=f"Empresa {i}",
            nome_fantasia=None, documento="11222333000181",
            tipo_pessoa="JURIDICA", inscricao_estadual=None,
            municipio="Fortaleza", uf="CE", cep=None,
            email=None, telefone=None, origem_sistema="FORTES",
        )
        for i in range(1, 4)
    ]
    loader = PostgresBinaryBulkLoader(_conninfo())
    with psycopg.connect(_conninfo()) as conn:
        with conn.transaction():
            n = loader.inserir_participantes(conn, None, empresa_id, itens)
        assert n == 3
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM erp.participante WHERE empresa_id = %s",
                (empresa_id,),
            )
            total = cur.fetchone()
            assert total is not None and total[0] == 3
        conn.execute("DELETE FROM erp.participante WHERE empresa_id = %s", (empresa_id,))
        conn.commit()
'''


# =====================================================================
#  CONFIG
# =====================================================================
G["config"]["requirements-web.txt"] = r'''# Web (painel Admin) — complementa o requirements.txt principal
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
jinja2>=3.1.0
python-multipart>=0.0.12
pytest-cov>=6.0.0
'''


G["config"]["pyproject.toml"] = r'''[project]
name = "erp-contabil-migracao"
version = "0.1.0"
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
"src/web/app.py" = ["B008"]  # FastAPI Depends()/File() em defaults
"scripts/*.py" = ["T201"]     # prints de CLI são o objetivo

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
        prefixo = {"ddl": "🗄️ ", "impl": "⚙️ ", "load": "⬇️ ",
                   "infra": "🏗️ ", "web": "🌐", "scripts": "📜",
                   "tests": "🧪", "config": "⚙️ "}[grupo]
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
            print(f"{prefixo} [SKIP]      {rel}")
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
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--backup", action="store_true")
    parser.add_argument(
        "--only",
        choices=["ddl", "impl", "load", "infra", "web", "scripts", "tests", "config", "all"],
        default="all",
    )
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
        tot_c += c
        tot_a += a
        tot_p += p

    print(f"\n📊 Criados: {tot_c}, Atualizados: {tot_a}, Pulados: {tot_p}")
    if args.dry_run:
        print("(dry-run — nada foi escrito)")
        return 0

    print("\nPróximos passos:")
    print("  1. pip install -r requirements-web.txt")
    print("  2. Aplicar DDL Stage 3 (se ainda não fez):")
    print("     python scripts/setup_db.py --ddl ddl/schema_stage3.sql")
    print("  3. Subir painel:")
    print("     ./scripts/run_admin.sh")
    print("     # abrir http://localhost:8000/admin/utilitarios/migracao")
    print("  4. Verificação final:")
    print("     pytest -v && mypy src/ && ruff check src/")
    print("\nTestes de integração (exigem Postgres):")
    print("  ERP_TEST_DATABASE_URL=postgresql://... pytest -m integration -v")
    return 0


if __name__ == "__main__":
    sys.exit(main())