#!/usr/bin/env python3
"""scaffold_python.py — Gera todos os arquivos .py do módulo de migração.

Uso:
    python scaffold_python.py                # cria apenas arquivos que ainda não existem
    python scaffold_python.py --force        # sobrescreve todos (use após editar manualmente!)
    python scaffold_python.py --dry-run      # só lista o que faria
    python scaffold_python.py --root /caminho  # diretório raiz (default: cwd)

Notes:
    - Os stubs contêm assinaturas completas com type hints, docstrings em português e
      `raise NotImplementedError("TODO: porta do C# ...")` no corpo.
    - Basta procurar por `TODO` no projeto e implementar arquivo por arquivo.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# =====================================================================
#  CONTEÚDO DOS ARQUIVOS
# =====================================================================
#  Organizado por camada. Cada chave é um caminho relativo ao projeto.
#  Valores são strings cruas (r'''...''') para não precisar escapar.
# =====================================================================
ARQUIVOS: dict[str, str] = {}


# ---------------------------------------------------------------------
#  Raiz e domínio
# ---------------------------------------------------------------------
ARQUIVOS["src/__init__.py"] = r'''"""ERP Contábil — Módulo de Migração.

Este pacote reúne os 4 motores de ETL (Extract, Transform, Load) e a
infraestrutura de orquestração para migrar dados de sistemas concorrentes
(Fortes Tecnologia / Tron Informática / SPED) para o banco local PostgreSQL.

Camadas:
    domain          → contratos, modelos e enums (sem dependências externas)
    extract         → conexão e leitura das bases de origem
    transform       → De-Para, validações contábeis e normalizações
    load            → inserção em alta performance + outbox do sincronizador delta
    infrastructure  → logger, retry, telemetria e orquestrador
    web             → painel do administrador
"""
'''

ARQUIVOS["src/domain/__init__.py"] = '"""Camada de domínio: contratos, modelos e enums do migrador."""\n'
ARQUIVOS["src/domain/contracts/__init__.py"] = '"""Contratos (interfaces) do domínio de migração."""\n'
ARQUIVOS["src/domain/models/__init__.py"] = '"""Modelos de dados do domínio de migração."""\n'
ARQUIVOS["src/domain/models/entities/__init__.py"] = '"""Entidades do domínio (origem e destino)."""\n'
ARQUIVOS["src/domain/enums/__init__.py"] = '"""Enumerações do domínio."""\n'


ARQUIVOS["src/domain/enums/enums.py"] = r'''"""Enumerações do domínio de migração."""
from __future__ import annotations

from enum import Enum


class OperacaoSync(str, Enum):
    """Operação a ser propagada para o Sincronizador Delta."""

    UPSERT = "UPSERT"
    DELETE = "DELETE"


class SeveridadeErro(str, Enum):
    """Severidade de um erro registrado no log de migração."""

    INFO = "INFO"
    AVISO = "AVISO"
    ERRO = "ERRO"
    FATAL = "FATAL"


class StatusMigracao(str, Enum):
    """Estado de um job de migração."""

    PENDENTE = "PENDENTE"
    EM_ANDAMENTO = "EM_ANDAMENTO"
    CONCLUIDO = "CONCLUIDO"
    CONCLUIDO_COM_ERROS = "CONCLUIDO_COM_ERROS"
    FALHOU = "FALHOU"
    CANCELADO = "CANCELADO"
'''


ARQUIVOS["src/domain/models/chunk.py"] = r'''"""Modelos de agregação usados pelos motores de ETL."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar

T = TypeVar("T")
U = TypeVar("U")


@dataclass(frozen=True, slots=True)
class Chunk(Generic[T]):
    """Lote de registros extraídos da origem.

    Attributes:
        itens: registros do lote (tipicamente 5.000).
        total_acumulado: quantos registros já foram extraídos desde o início.
    """

    itens: list[T]
    total_acumulado: int


@dataclass(frozen=True, slots=True)
class TransformResult(Generic[U]):
    """Resultado de uma transformação — sucesso (com valor) ou falha (com motivo)."""

    sucesso: bool
    valor: U | None = None
    motivo: str | None = None

    @classmethod
    def ok(cls, valor: U) -> "TransformResult[U]":
        """Cria um resultado de sucesso."""
        return cls(sucesso=True, valor=valor)

    @classmethod
    def falha(cls, motivo: str) -> "TransformResult[U]":
        """Cria um resultado de falha (vai para quarentena)."""
        return cls(sucesso=False, motivo=motivo)


@dataclass(frozen=True, slots=True)
class ResultadoValidacaoPlano:
    """Resultado da validação contábil do plano de contas."""

    valido: bool
    erros: list[str] = field(default_factory=list)
'''


ARQUIVOS["src/domain/models/migration_options.py"] = r'''"""Opções de configuração das migrações."""
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
    trust_server_certificate: bool = False
    timeout_conexao_s: int = 10
    tamanho_chunk: int = Field(default=5_000, ge=100, le=50_000)


@dataclass(frozen=True, slots=True)
class MigrationOptions:
    """Opções gerais de uma execução de migração."""

    empresa_id: str
    origem: str                              # "FORTES" | "TRON" | "SPED"
    dry_run: bool = False
    parar_no_primeiro_erro: bool = False
    caminho_log: str = "migracao_erros.log"
    caminho_quarentena: str = "migracao_quarentena.jsonl"
'''


ARQUIVOS["src/domain/models/migration_progress.py"] = r'''"""Modelo de progresso reportado à UI do Admin."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MigrationProgress:
    """Instantâneo do progresso de uma migração."""

    etapa_atual: str = ""
    registros_processados: int = 0
    registros_com_erro: int = 0
    percentual: float = 0.0
'''


ARQUIVOS["src/domain/models/migration_result.py"] = r'''"""Resultado consolidado de um job de migração."""
from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.enums.enums import StatusMigracao


@dataclass(slots=True)
class MigrationResult:
    """Resumo final de um job de migração."""

    job_id: str
    empresa_id: str
    sucesso: bool = False
    status: StatusMigracao = StatusMigracao.PENDENTE
    importados: int = 0
    erros: int = 0
    ignorados: int = 0
    duracao_segundos: float = 0.0
    log: list[str] = field(default_factory=list)
'''


ARQUIVOS["src/domain/models/entities/participante.py"] = r'''"""Entidades de participante (cliente/fornecedor)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParticipanteOrigem:
    """Registro bruto extraído da base de origem (Fortes/Tron)."""

    codigo_origem: int
    razao_social: str | None
    nome_fantasia: str | None
    documento: str | None
    inscricao_estadual: str | None
    inscricao_municipal: str | None
    endereco: str | None
    cidade: str | None
    uf: str | None
    cep: str | None
    email: str | None
    telefone: str | None
    tipo_pessoa: str | None


@dataclass(frozen=True, slots=True)
class ParticipanteDestino:
    """Registro já validado e normalizado, pronto para o INSERT."""

    codigo_origem: int
    razao_social: str
    nome_fantasia: str | None
    documento: str
    tipo_pessoa: str                # "FISICA" | "JURIDICA"
    inscricao_estadual: str | None
    municipio: str | None
    uf: str | None
    cep: str | None
    email: str | None
    telefone: str | None
    origem_sistema: str             # "FORTES" | "TRON" | "SPED"
'''


ARQUIVOS["src/domain/models/entities/conta_contabil.py"] = r'''"""Entidades do plano de contas contábil."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ContaContabil:
    """Uma conta do plano de contas — sintética ou analítica.

    Attributes:
        codigo: código contábil (ex.: "1.1.01.001").
        nome: descrição da conta.
        codigo_pai: código do pai na hierarquia (None para raiz).
        natureza: "SINTETICA" ou "ANALITICA".
        grau: profundidade na árvore (raiz = 1).
        natureza_saldo: "DEVEDORA" ou "CREDORA" — obrigatório se analítica.
    """

    codigo: str
    nome: str
    codigo_pai: str | None
    natureza: str
    grau: int
    natureza_saldo: str | None
'''


ARQUIVOS["src/domain/models/entities/sped_registro.py"] = r'''"""Registro genérico de um arquivo SPED."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SpedRegistro:
    """Linha do SPED Fiscal já fatiada em (código do registro, campos).

    Attributes:
        codigo: código do registro SPED (ex.: "0150", "C100").
        campos: campos do registro, sem o pipe inicial/final.
        linha_bruta: linha original do arquivo (para logs de erro).
    """

    codigo: str
    campos: tuple[str, ...]
    linha_bruta: str
'''


ARQUIVOS["src/domain/models/entities/empresa.py"] = r'''"""Entidade empresa (cadastro de CNPJ do escritório/cliente)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EmpresaOrigem:
    """Registro bruto de empresa extraído da base de origem."""

    codigo_origem: int
    razao_social: str | None
    cnpj: str | None
    uf: str | None
    regime_tributario: str | None
'''


# ---------------------------------------------------------------------
#  Contratos (Protocols)
# ---------------------------------------------------------------------
ARQUIVOS["src/domain/contracts/extractor.py"] = r'''"""Contrato do motor de extração (Camada 2)."""
from __future__ import annotations

import threading
from collections.abc import Iterator
from typing import Generic, Protocol, TypeVar

from src.domain.models.chunk import Chunk

T = TypeVar("T")


class IEntityExtractor(Protocol[T]):
    """Extrai registros de uma base de origem em lotes (chunks).

    Notes:
        - `stop_event`: evento sinalizado externamente para interromper a extração.
        - Todo extrator é `Iterator` (streaming) — nunca carrega a tabela inteira em RAM.
        - A paginação por keyset (`WHERE id > @ultimo`) é responsabilidade da implementação.
    """

    def extract(
        self, stop_event: threading.Event | None = None
    ) -> Iterator[Chunk[T]]:
        """Itera sobre os registros em lotes de até `tamanho_chunk`."""
        ...
'''


ARQUIVOS["src/domain/contracts/transformer.py"] = r'''"""Contrato do motor de transformação (Camada 3)."""
from __future__ import annotations

from typing import Generic, Protocol, TypeVar

from src.domain.models.chunk import TransformResult

S = TypeVar("S")
D = TypeVar("D")


class IEntityTransformer(Protocol[S, D]):
    """Transforma e valida um registro origem → destino."""

    def transform(self, origem: S) -> TransformResult[D]:
        """Aplica De-Para, normalizações e validações contábeis.

        Returns:
            TransformResult.ok(destino) se válido, ou
            TransformResult.falha(motivo) — caso em que o registro vai para quarentena.
        """
        ...
'''


ARQUIVOS["src/domain/contracts/loader.py"] = r'''"""Contrato do motor de inserção de alta performance (Camada 4)."""
from __future__ import annotations

from typing import TYPE_CHECKING, Generic, Protocol, TypeVar

if TYPE_CHECKING:
    import psycopg

T = TypeVar("T")


class IEntityLoader(Protocol[T]):
    """Insere um lote de registros no PostgreSQL local."""

    def load(
        self,
        conn: "psycopg.Connection",
        tx: "psycopg.Transaction",
        empresa_id: str,
        itens: list[T],
    ) -> int:
        """Executa o INSERT em lote. Retorna quantos registros foram inseridos."""
        ...
'''


ARQUIVOS["src/domain/contracts/orchestrator.py"] = r'''"""Contrato do orquestrador de migração."""
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
'''


# ---------------------------------------------------------------------
#  Camada Extract
# ---------------------------------------------------------------------
ARQUIVOS["src/extract/__init__.py"] = '"""Motores de extração (camada 2)."""\n'
ARQUIVOS["src/extract/fortes/__init__.py"] = '"""Extração a partir do SQL Server da Fortes Tecnologia."""\n'
ARQUIVOS["src/extract/tron/__init__.py"] = '"""Extração a partir da Tron Informática (Firebird) e arquivos SPED."""\n'
ARQUIVOS["src/extract/shared/__init__.py"] = '"""Helpers compartilhados entre extractors."""\n'


ARQUIVOS["src/extract/fortes/connection.py"] = r'''"""Fábrica de conexão com o SQL Server da Fortes Tecnologia."""
from __future__ import annotations

import contextlib
from collections.abc import Iterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pymssql

from src.domain.models.migration_options import FortesConnectionOptions


class FortesConnectionFactory:
    """Cria conexões curtas e identificáveis com o SQL Server da Fortes.

    Notes:
        - NÃO abrir um pool grande: o banco é do cliente. Abrir/fechar por chunk
          evita travar o ERP enquanto ele trabalha.
        - `ApplicationName` permite ao DBA identificar as sessões do migrador.
        - `TrustServerCertificate=True` é útil em ambientes com certificado self-signed.
    """

    def __init__(self, opt: FortesConnectionOptions) -> None:
        self._opt = opt

    def build_connection_string(self) -> str:
        """Monta a connection string a partir das opções."""
        raise NotImplementedError("TODO: porta do C# FortesConnectionFactory.BuildConnectionString")

    @contextlib.contextmanager
    def open(self) -> Iterator["pymssql.Connection"]:
        """Abre a conexão e garante fechamento ao sair do bloco `with`."""
        raise NotImplementedError("TODO: porta do C# FortesConnectionFactory.OpenAsync")
        yield  # pragma: no cover
'''


ARQUIVOS["src/extract/fortes/schema_discovery.py"] = r'''"""Descoberta do schema real da Fortes antes de mapear colunas."""
from __future__ import annotations

from dataclasses import dataclass

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
    """Lista tabelas e colunas da Fortes para confirmar o De-Para na UI.

    Notes:
        Os nomes de tabela da Fortes variam por versão e por módulo licenciado.
        Em vez de chutar, o migrador primeiro descobre o schema real e o admin
        confirma o De-Para na tela antes de disparar a carga.
    """

    def __init__(self, factory: FortesConnectionFactory) -> None:
        self._factory = factory

    def descobrir(self) -> list[TabelaDescoberta]:
        """Executa INFORMATION_SCHEMA e retorna os metadados de todas as tabelas."""
        raise NotImplementedError("TODO: porta do C# FortesSchemaDiscovery.Descobrir")
'''


ARQUIVOS["src/extract/fortes/participante_extractor.py"] = r'''"""Extrator de participantes (clientes/fornecedores) da Fortes."""
from __future__ import annotations

import threading
from collections.abc import Iterator

from src.domain.contracts.extractor import IEntityExtractor
from src.domain.models.chunk import Chunk
from src.domain.models.entities.participante import ParticipanteOrigem
from src.extract.fortes.connection import FortesConnectionFactory


class FortesParticipanteExtractor(IEntityExtractor[ParticipanteOrigem]):
    """Extrai participantes usando keyset pagination + WITH (NOLOCK).

    Chunking:
        SELECT ... FROM PARTICIPANTE P WITH (NOLOCK)
        WHERE P.CODIGO > @ultimo
        ORDER BY P.CODIGO
        OFFSET 0 ROWS FETCH NEXT @take ROWS ONLY

    Notes:
        Keyset (WHERE CODIGO > @ultimo) é O(log n) e não degrada em tabelas grandes,
        ao contrário de OFFSET alto. Requer índice em CODIGO (normalmente PK).
    """

    def __init__(
        self, factory: FortesConnectionFactory, tamanho_chunk: int = 5_000
    ) -> None:
        self._factory = factory
        self._tamanho_chunk = tamanho_chunk

    def extract(
        self, stop_event: threading.Event | None = None
    ) -> Iterator[Chunk[ParticipanteOrigem]]:
        """Itera sobre PARTICIPANTE em lotes de até `tamanho_chunk`."""
        raise NotImplementedError(
            "TODO: porta do C# FortesParticipanteExtractor.ExtractAsync"
        )
        yield  # pragma: no cover
'''


ARQUIVOS["src/extract/fortes/empresa_extractor.py"] = r'''"""Extrator do cadastro de empresas da Fortes."""
from __future__ import annotations

import threading
from collections.abc import Iterator

from src.domain.contracts.extractor import IEntityExtractor
from src.domain.models.chunk import Chunk
from src.domain.models.entities.empresa import EmpresaOrigem
from src.extract.fortes.connection import FortesConnectionFactory


class FortesEmpresaExtractor(IEntityExtractor[EmpresaOrigem]):
    """Extrai o cadastro de EMPRESA da Fortes."""

    def __init__(
        self, factory: FortesConnectionFactory, tamanho_chunk: int = 5_000
    ) -> None:
        self._factory = factory
        self._tamanho_chunk = tamanho_chunk

    def extract(
        self, stop_event: threading.Event | None = None
    ) -> Iterator[Chunk[EmpresaOrigem]]:
        """Itera sobre EMPRESA em lotes."""
        raise NotImplementedError("TODO: porta do C# FortesEmpresaExtractor")
        yield  # pragma: no cover
'''


ARQUIVOS["src/extract/fortes/plano_contas_extractor.py"] = r'''"""Extrator do plano de contas contábil da Fortes."""
from __future__ import annotations

import threading
from collections.abc import Iterator

from src.domain.contracts.extractor import IEntityExtractor
from src.domain.models.chunk import Chunk
from src.domain.models.entities.conta_contabil import ContaContabil
from src.extract.fortes.connection import FortesConnectionFactory


class FortesPlanoContasExtractor(IEntityExtractor[ContaContabil]):
    """Extrai o plano de contas (sintéticas + analíticas) da Fortes."""

    def __init__(
        self, factory: FortesConnectionFactory, tamanho_chunk: int = 5_000
    ) -> None:
        self._factory = factory
        self._tamanho_chunk = tamanho_chunk

    def extract(
        self, stop_event: threading.Event | None = None
    ) -> Iterator[Chunk[ContaContabil]]:
        """Itera sobre o plano de contas em lotes."""
        raise NotImplementedError("TODO: porta do C# FortesPlanoContasExtractor")
        yield  # pragma: no cover
'''


ARQUIVOS["src/extract/tron/firebird_extractor.py"] = r'''"""Extrator da base Firebird da Tron Informática."""
from __future__ import annotations

import threading
from collections.abc import Iterator
from dataclasses import dataclass

from src.domain.models.chunk import Chunk


@dataclass(frozen=True, slots=True)
class TronConnectionOptions:
    """Credenciais do Firebird da Tron."""

    host: str
    porta: int = 3050
    database: str        # caminho do .fdb
    usuario: str
    senha: str
    charset: str = "UTF8"


class TronFirebirdExtractor:
    """Extrai registros da Tron via Firebird (participantes, plano, NFs).

    Notes:
        O schema da Tron varia bastante por versão. Recomenda-se rodar primeiro
        uma descoberta de schema análoga à FortesSchemaDiscovery antes de mapear.
    """

    def __init__(
        self, opt: TronConnectionOptions, tamanho_chunk: int = 5_000
    ) -> None:
        self._opt = opt
        self._tamanho_chunk = tamanho_chunk

    def extract_participantes(
        self, stop_event: threading.Event | None = None
    ) -> Iterator[Chunk[object]]:
        """Extrai participantes da Tron (schema varia — descoberta necessária)."""
        raise NotImplementedError("TODO: porta do C# TronFirebirdExtractor")
        yield  # pragma: no cover
'''


ARQUIVOS["src/extract/tron/sped_txt_extractor.py"] = r'''"""Extrator de registros a partir de arquivos .txt do SPED Fiscal/Contribuições."""
from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path

from src.domain.contracts.extractor import IEntityExtractor
from src.domain.models.chunk import Chunk
from src.domain.models.entities.sped_registro import SpedRegistro


class SpedTxtExtractor(IEntityExtractor[SpedRegistro]):
    """Lê um arquivo SPED e emite apenas os registros de cadastro relevantes.

    Registros emitidos: 0000, 0150, 0190, 0200, 0500, C100, C170.

    Notes:
        O e-Fisco Ceará não expõe API pública de download. O caminho realista é:
        (a) o cliente baixar os .txt do SPED no portal da Receita/SEFAZ e subir
        no painel, ou (b) baixar XMLs de NF-e no portal nacional. Não faça
        scraping/automação de login no e-CAC com credencial de terceiro sem
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
        """Itera linha a linha, ignorando registros fora do conjunto de interesse."""
        raise NotImplementedError("TODO: porta do C# SpedTxtExtractor.ExtractAsync")
        yield  # pragma: no cover
'''


ARQUIVOS["src/extract/shared/sqlserver_chunk_reader.py"] = r'''"""Helper genérico de paginação por keyset para SQL Server."""
from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from typing import Any


class SqlServerChunkReader:
    """Lê tabelas grandes do SQL Server em lotes por keyset.

    O `sql_template` deve conter `{ultimo}` e `{take}` como placeholders,
    por exemplo:
        SELECT * FROM TABELA WITH (NOLOCK)
        WHERE ID > {ultimo} ORDER BY ID
        OFFSET 0 ROWS FETCH NEXT {take} ROWS ONLY
    """

    def __init__(self, tamanho_chunk: int = 5_000) -> None:
        self._tamanho_chunk = tamanho_chunk

    def ler(
        self,
        conn: Any,
        sql_template: str,
        coluna_chave: str,
        mapear: Callable[[Any], Any],
        stop_event: threading.Event | None = None,
    ) -> Iterator[list[Any]]:
        """Executa `sql_template` repetidamente, avançando a chave."""
        raise NotImplementedError("TODO: porta do C# SqlServerChunkReader")
        yield  # pragma: no cover
'''


ARQUIVOS["src/extract/shared/file_chunk_reader.py"] = r'''"""Helper para leitura de arquivos grandes em chunks de linhas."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path


class FileChunkReader:
    """Lê um arquivo de texto em lotes de N linhas."""

    def __init__(self, tamanho_chunk: int = 5_000, encoding: str = "utf-8") -> None:
        self._tamanho_chunk = tamanho_chunk
        self._encoding = encoding

    def ler(self, caminho: Path) -> Iterator[list[str]]:
        """Itera sobre o arquivo em lotes de linhas."""
        raise NotImplementedError("TODO: porta do C# FileChunkReader")
        yield  # pragma: no cover
'''


# ---------------------------------------------------------------------
#  Camada Transform
# ---------------------------------------------------------------------
ARQUIVOS["src/transform/__init__.py"] = '"""Motor de transformação e validação (camada 3)."""\n'
ARQUIVOS["src/transform/mappings/__init__.py"] = '"""Dicionários De-Para origem → ERP."""\n'
ARQUIVOS["src/transform/validators/__init__.py"] = '"""Validadores de CPF/CNPJ, plano de contas e participantes."""\n'
ARQUIVOS["src/transform/sped/__init__.py"] = '"""Parser e leitor de blocos do SPED."""\n'
ARQUIVOS["src/transform/normalizers/__init__.py"] = '"""Normalizadores de texto, documento, UF, e-mail e telefone."""\n'


ARQUIVOS["src/transform/mappings/fortes_para_erp_map.py"] = r'''"""Dicionário De-Para Fortes → ERP."""
from __future__ import annotations


class FortesParaErpMap:
    """Mapeamento de colunas da Fortes para o schema do ERP.

    Notes:
        Os nomes de coluna à esquerda são os da Fortes (variam por versão).
        Rode FortesSchemaDiscovery primeiro e ajuste aqui o que divergir.
    """

    PARTICIPANTE: dict[str, str] = {
        "CODIGO":        "codigo_origem",
        "RAZAO_SOCIAL":  "razao_social",
        "NOME_FANTASIA": "nome_fantasia",
        "CNPJ_CPF":      "documento",
        "IE":            "inscricao_estadual",
        "IM":            "inscricao_municipal",
        "ENDERECO":      "logradouro",
        "CIDADE":        "municipio",
        "UF":            "uf",
        "CEP":           "cep",
        "EMAIL":         "email",
        "TELEFONE":      "telefone",
        "TIPO_PESSOA":   "tipo_pessoa",
    }

    @staticmethod
    def tipo_pessoa(origem: str | None) -> str:
        """Normaliza J/F/PJ/PF → JURIDICA/FISICA (default JURIDICA)."""
        raise NotImplementedError("TODO: porta do C# FortesParaErpMap.TipoPessoa")
'''


ARQUIVOS["src/transform/mappings/sped_para_erp_map.py"] = r'''"""Dicionário De-Para SPED → ERP."""
from __future__ import annotations


class SpedParaErpMap:
    """Mapeamento de campos dos registros SPED para o schema do ERP.

    Notes:
        Os índices referem-se à posição do campo no registro SPED (a partir de 1),
        conforme o Guia Prático do SPED Fiscal.
    """

    # 0150 — Participantes
    R0150: dict[int, str] = {
        2: "codigo_origem",
        3: "razao_social",
        5: "documento",     # CPF/CNPJ
        6: "uf",
        7: "inscricao_estadual",
        9: "municipio",
        11: "logradouro",
    }

    # 0500 — Plano de contas
    R0500: dict[int, str] = {
        2: "codigo",
        3: "natureza",      # 01=Sintética, 02=Analítica
        4: "nome",
        6: "grau",
    }
'''


ARQUIVOS["src/transform/validators/cpf_cnpj.py"] = r'''"""Validação de CPF e CNPJ pelo dígito verificador."""
from __future__ import annotations


class CpfCnpjValidator:
    """Algoritmo oficial de validação de CPF/CNPJ (com checksum, não só máscara)."""

    @staticmethod
    def somente_digitos(doc: str | None) -> str:
        """Remove tudo que não for dígito."""
        raise NotImplementedError("TODO: porta do C# CpfCnpjValidator.SomenteDigitos")

    @staticmethod
    def cpf_valido(cpf: str) -> bool:
        """Verifica os dois dígitos verificadores do CPF."""
        raise NotImplementedError("TODO: porta do C# CpfCnpjValidator.CpfValido")

    @staticmethod
    def cnpj_valido(cnpj: str) -> bool:
        """Verifica os dois dígitos verificadores do CNPJ."""
        raise NotImplementedError("TODO: porta do C# CpfCnpjValidator.CnpjValido")

    @classmethod
    def validar(cls, doc: str | None, tipo_pessoa: str) -> tuple[bool, str | None]:
        """Valida e retorna (ok, motivo_rejeicao)."""
        raise NotImplementedError("TODO: porta do C# CpfCnpjValidator.Validar")
'''


ARQUIVOS["src/transform/validators/plano_contas.py"] = r'''"""Validação contábil do plano de contas."""
from __future__ import annotations

from src.domain.models.chunk import ResultadoValidacaoPlano
from src.domain.models.entities.conta_contabil import ContaContabil


class PlanoContasValidator:
    """Regras mínimas de consistência do plano de contas.

    Regras (portadas do C#):
        1. Sintética DEVE ter ao menos um filho.
        2. Analítica NÃO pode ter filhos (é onde os lançamentos batem).
        3. Todo codigo_pai deve existir na lista.
        4. Não pode haver ciclo (A→B→A).
        5. Grau do filho = grau do pai + 1.
        6. Natureza de saldo obrigatória na analítica.
    """

    @staticmethod
    def validar(contas: list[ContaContabil]) -> ResultadoValidacaoPlano:
        """Verifica sintéticas/analíticas, pai existente, ciclo, grau e natureza de saldo."""
        raise NotImplementedError("TODO: porta do C# PlanoContasValidator.Validar")
'''


ARQUIVOS["src/transform/validators/participante.py"] = r'''"""Validação de participantes antes do load."""
from __future__ import annotations

from src.domain.models.entities.participante import ParticipanteDestino


class ParticipanteValidator:
    """Regras de negócio sobre um participante já normalizado."""

    @staticmethod
    def validar(p: ParticipanteDestino) -> tuple[bool, str | None]:
        """Valida documento (CPF/CNPJ), UF e razão social."""
        raise NotImplementedError("TODO: porta do C# ParticipanteValidator")
'''


ARQUIVOS["src/transform/normalizers/normalizers.py"] = r'''"""Normalizações de texto, documento, UF, e-mail e telefone."""
from __future__ import annotations


class Normalizers:
    """Funções puras de normalização de campos."""

    @staticmethod
    def texto(v: str | None) -> str | None:
        """Trim, colapsa espaços, retorna None se vazio."""
        raise NotImplementedError("TODO: porta do C# Normalizers.Texto")

    @staticmethod
    def documento(v: str | None) -> str | None:
        """Mantém só dígitos."""
        raise NotImplementedError("TODO: porta do C# Normalizers.Documento")

    @staticmethod
    def uf(v: str | None) -> str | None:
        """Uppercase, valida contra a lista de UFs do IBGE."""
        raise NotImplementedError("TODO: porta do C# Normalizers.Uf")

    @staticmethod
    def email(v: str | None) -> str | None:
        """Lowercase e trim."""
        raise NotImplementedError("TODO: porta do C# Normalizers.Email")

    @staticmethod
    def telefone(v: str | None) -> str | None:
        """Mantém dígitos e o '+' inicial."""
        raise NotImplementedError("TODO: porta do C# Normalizers.Telefone")
'''


ARQUIVOS["src/transform/sped/parser.py"] = r'''"""Parser de linhas do SPED."""
from __future__ import annotations

from src.domain.models.entities.sped_registro import SpedRegistro


class SpedLineParser:
    """Converte uma linha bruta do SPED em SpedRegistro.

    Formato: |REG|campo1|campo2|...|
    """

    @staticmethod
    def parse(linha: str) -> SpedRegistro | None:
        """Retorna None se a linha for inválida (vazia ou sem pipes)."""
        raise NotImplementedError("TODO: porta do C# SpedLineParser")
'''


ARQUIVOS["src/transform/sped/block_reader.py"] = r'''"""Leitor de blocos do SPED (0000, 0150, C100...)."""
from __future__ import annotations

from collections.abc import Iterator

from src.domain.models.entities.sped_registro import SpedRegistro


class SpedBlockReader:
    """Filtra registros do SPED por bloco."""

    def __init__(self, registros: Iterator[SpedRegistro]) -> None:
        self._registros = registros

    def por_bloco(self, bloco: str) -> Iterator[SpedRegistro]:
        """Retorna apenas registros cujo código começa pelo bloco (ex.: 'C')."""
        raise NotImplementedError("TODO: porta do C# SpedBlockReader")
        yield  # pragma: no cover
'''


ARQUIVOS["src/transform/participante_transformer.py"] = r'''"""Transformer participante origem → destino."""
from __future__ import annotations

from src.domain.contracts.transformer import IEntityTransformer
from src.domain.models.chunk import TransformResult
from src.domain.models.entities.participante import (
    ParticipanteDestino,
    ParticipanteOrigem,
)
from src.infrastructure.logging.migration_logger import MigrationLogger


class ParticipanteTransformer(
    IEntityTransformer[ParticipanteOrigem, ParticipanteDestino]
):
    """Aplica De-Para, normalizações e valida CPF/CNPJ."""

    def __init__(self, logger: MigrationLogger) -> None:
        self._logger = logger

    def transform(
        self, origem: ParticipanteOrigem
    ) -> TransformResult[ParticipanteDestino]:
        """Retorna TransformResult.ok(destino) ou TransformResult.falha(motivo)."""
        raise NotImplementedError(
            "TODO: porta do C# ParticipanteTransformer.Transform"
        )
'''


# ---------------------------------------------------------------------
#  Camada Load
# ---------------------------------------------------------------------
ARQUIVOS["src/load/__init__.py"] = '"""Motor de inserção de alta performance (camada 4)."""\n'


ARQUIVOS["src/load/postgres_bulk_loader.py"] = r'''"""Bulk Insert no PostgreSQL via COPY ... FROM STDIN (FORMAT BINARY)."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import psycopg

from src.domain.models.entities.participante import ParticipanteDestino


class PostgresBinaryBulkLoader:
    """Insere grandes volumes em poucos round-trips via COPY BINARY.

    Notes:
        COPY é tudo-ou-nada. Se uma linha violar constraint, o lote inteiro
        aborta. Por isso o orquestrador cai para PostgresFallbackRowLoader,
        que isola o registro ruim com SAVEPOINT.
    """

    def __init__(self, connection_string: str) -> None:
        self._connection_string = connection_string

    def inserir_participantes(
        self,
        conn: "psycopg.Connection",
        tx: "psycopg.Transaction",
        empresa_id: str,
        itens: list[ParticipanteDestino],
    ) -> int:
        """Executa COPY BINARY. Retorna o número de linhas inseridas."""
        raise NotImplementedError(
            "TODO: porta do C# PostgresBinaryBulkLoader.InserirParticipantesAsync"
        )
'''


ARQUIVOS["src/load/postgres_fallback_loader.py"] = r'''"""Fallback linha-a-linha com SAVEPOINT para o caso de COPY falhar."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import psycopg

from src.domain.models.entities.participante import ParticipanteDestino
from src.infrastructure.logging.migration_logger import MigrationLogger


class PostgresFallbackRowLoader:
    """Insere linha a linha dentro de SAVEPOINTs, isolando registros ruins."""

    def __init__(self, logger: MigrationLogger) -> None:
        self._logger = logger

    def inserir_participantes(
        self,
        conn: "psycopg.Connection",
        tx: "psycopg.Transaction",
        empresa_id: str,
        itens: list[ParticipanteDestino],
    ) -> int:
        """Retorna quantos registros foram inseridos com sucesso."""
        raise NotImplementedError("TODO: porta do C# PostgresFallbackRowLoader")
'''


ARQUIVOS["src/load/sync_outbox_writer.py"] = r'''"""Escritor do Transactional Outbox (padrão Outbox) para o Sincronizador Delta."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import psycopg

from src.domain.enums.enums import OperacaoSync


class SyncOutboxWriter:
    """Enfileira eventos de sincronização na MESMA transação do Load.

    Notes:
        Se a transação commitar, o evento de delta é garantidamente enfileirado.
        Elimina o bug clássico de "importei mas a nuvem não soube".
    """

    def enfileirar(
        self,
        conn: "psycopg.Connection",
        tx: "psycopg.Transaction",
        entidade: str,
        registro_id: str,
        operacao: OperacaoSync,
    ) -> None:
        """INSERT em sync.sync_outbox (mesma tx do Load)."""
        raise NotImplementedError(
            "TODO: porta do C# SyncOutboxWriter.EnfileirarAsync"
        )
'''


# ---------------------------------------------------------------------
#  Camada Infrastructure
# ---------------------------------------------------------------------
ARQUIVOS["src/infrastructure/__init__.py"] = '"""Infraestrutura: logger, retry, telemetria e orquestrador."""\n'
ARQUIVOS["src/infrastructure/logging/__init__.py"] = '"""Logger resiliente."""\n'
ARQUIVOS["src/infrastructure/resilience/__init__.py"] = '"""Políticas de retry."""\n'
ARQUIVOS["src/infrastructure/telemetry/__init__.py"] = '"""Métricas de execução."""\n'


ARQUIVOS["src/infrastructure/logging/migration_logger.py"] = r'''"""Logger resiliente que grava em migracao_erros.log (JSONL) e na tabela migracao.erro."""
from __future__ import annotations

from pathlib import Path

from src.domain.models.migration_result import MigrationResult


class MigrationLogger:
    """Escreve erros em arquivo JSONL e na tabela migracao.erro.

    Formato do arquivo (uma linha por erro):
        {"ts": "...", "entidade": "...", "registroId": "...", "mensagem": "...",
         "stack": "...", "maquina": "..."}

    Notes:
        - Thread-safe via asyncio.Lock / threading.Lock.
        - Grava SEMPRE em disco (mesmo se o INSERT no banco falhar).
        - O INSERT na tabela é best-effort; a auditoria é o arquivo.
    """

    def __init__(self, caminho_log: Path, connection_string: str) -> None:
        self._caminho_log = caminho_log
        self._connection_string = connection_string

    def iniciar_job(self, job_id: str, origem: str) -> None:
        """Registra o início de um job."""
        raise NotImplementedError("TODO: porta do C# MigrationLogger.IniciarJobAsync")

    def erro(
        self,
        entidade: str,
        registro_id: str,
        mensagem: str,
        excecao: BaseException | None = None,
    ) -> None:
        """Grava uma linha de erro em JSONL + INSERT em migracao.erro."""
        raise NotImplementedError("TODO: porta do C# MigrationLogger.ErroAsync")

    def finalizar_job(self, job_id: str, resultado: MigrationResult) -> None:
        """Registra o término do job (sucesso/falha, contagens, duração)."""
        raise NotImplementedError(
            "TODO: porta do C# MigrationLogger.FinalizarJobAsync"
        )
'''


ARQUIVOS["src/infrastructure/resilience/retry_policy.py"] = r'''"""Política de retry com backoff exponencial."""
from __future__ import annotations

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
        self._tentativas = tentativas
        self._backoff_inicial_s = backoff_inicial_s
        self._fator = fator
        self._max_backoff_s = max_backoff_s

    def executar(self, fn: Callable[[], T]) -> T:
        """Executa `fn`; em caso de exceção, espera e tenta de novo."""
        raise NotImplementedError("TODO: porta do C# RetryPolicy")
'''


ARQUIVOS["src/infrastructure/telemetry/metrics.py"] = r'''"""Métricas de execução do migrador."""
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
        """Atualiza os contadores após um chunk."""
        raise NotImplementedError("TODO: porta do C# MigrationMetrics")
'''


ARQUIVOS["src/infrastructure/orchestrator.py"] = r'''"""Orquestrador: coordena Extract → Transform → Load e publica no outbox."""
from __future__ import annotations

from collections.abc import Callable

from src.domain.contracts.orchestrator import IMigrationOrchestrator
from src.domain.models.migration_options import FortesConnectionOptions
from src.domain.models.migration_progress import MigrationProgress
from src.domain.models.migration_result import MigrationResult


class MigrationOrchestrator(IMigrationOrchestrator):
    """Implementação principal do pipeline de migração.

    Fluxo:
        1. Extrai em chunks da origem.
        2. Transforma cada item; o que falhar vai para quarentena (não para o COPY).
        3. Insere em lote no PostgreSQL local (uma transação por chunk).
        4. Enfileira evento no outbox na MESMA transação.
        5. Ao final, dispara FullSync para o Sincronizador Delta.
    """

    def __init__(
        self,
        fortes_factory: object,             # FortesConnectionFactory
        participante_extractor: object,     # FortesParticipanteExtractor
        participante_transformer: object,   # ParticipanteTransformer
        bulk_loader: object,                # PostgresBinaryBulkLoader
        fallback_loader: object,            # PostgresFallbackRowLoader
        outbox: object,                     # SyncOutboxWriter
        logger: object,                     # MigrationLogger
        data_source: object,                # psycopg_pool.ConnectionPool / DataSource
    ) -> None:
        self._fortes_factory = fortes_factory
        self._participante_extractor = participante_extractor
        self._participante_transformer = participante_transformer
        self._bulk_loader = bulk_loader
        self._fallback_loader = fallback_loader
        self._outbox = outbox
        self._logger = logger
        self._data_source = data_source

    def testar_conexao_fortes(self, opt: FortesConnectionOptions) -> bool:
        """Abre e fecha uma conexão rápida para validar credenciais."""
        raise NotImplementedError(
            "TODO: porta do C# MigrationOrchestrator.TestarConexaoFortesAsync"
        )

    def executar_migracao_fortes(
        self,
        opt: FortesConnectionOptions,
        progresso: Callable[[MigrationProgress], None],
    ) -> MigrationResult:
        """Executa o pipeline completo para a origem Fortes."""
        raise NotImplementedError(
            "TODO: porta do C# MigrationOrchestrator.ExecutarMigracaoFortesAsync"
        )

    def executar_migracao_arquivos(
        self,
        caminhos: list[str],
        empresa_id: str,
        progresso: Callable[[MigrationProgress], None],
    ) -> MigrationResult:
        """Executa o pipeline a partir de arquivos .txt/.xml."""
        raise NotImplementedError(
            "TODO: porta do C# MigrationOrchestrator.ExecutarMigracaoArquivosAsync"
        )
'''


# ---------------------------------------------------------------------
#  Camada Web (FastAPI + Jinja2)
# ---------------------------------------------------------------------
ARQUIVOS["src/web/__init__.py"] = '"""Painel Admin do migrador."""\n'


ARQUIVOS["src/web/app.py"] = r'''"""Painel Admin — Utilitários de Migração (FastAPI + Jinja2).

Rodar com:
    uvicorn src.web.app:app --reload --port 8000
Acessar:
    http://localhost:8000/admin/utilitarios/migracao
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

app = FastAPI(title="ERP Contábil — Admin")
templates = Jinja2Templates(directory="src/web/templates")


@app.get("/admin/utilitarios/migracao", response_class=HTMLResponse)
def pagina_migracao(request: Request) -> HTMLResponse:
    """Renderiza a tela de utilitários de migração."""
    raise NotImplementedError("TODO: porta do C# UtilitariosMigracao.razor")
    return templates.TemplateResponse(
        "utilitarios_migracao.html", {"request": request}
    )


@app.post("/admin/utilitarios/migracao/fortes")
def iniciar_migracao_fortes() -> dict[str, str]:
    """Inicia a migração a partir do SQL Server da Fortes."""
    raise NotImplementedError("TODO: porta do C# IniciarFortes")


@app.post("/admin/utilitarios/migracao/arquivos")
def iniciar_migracao_arquivos() -> dict[str, str]:
    """Inicia a migração a partir de upload de arquivos SPED/NF-e."""
    raise NotImplementedError("TODO: porta do C# IniciarArquivos")
'''


ARQUIVOS["src/web/templates/utilitarios_migracao.html"] = r'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Migração — Admin</title>
</head>
<body>
  <h1>Utilitários do Admin — Migração de Dados</h1>
  <!-- TODO: porta do C# UtilitariosMigracao.razor -->
</body>
</html>
'''


# ---------------------------------------------------------------------
#  Testes
# ---------------------------------------------------------------------
ARQUIVOS["tests/__init__.py"] = '"""Testes do módulo de migração."""\n'


ARQUIVOS["tests/test_cpf_cnpj.py"] = r'''"""Testes de validação de CPF/CNPJ."""
from __future__ import annotations

import pytest

from src.transform.validators.cpf_cnpj import CpfCnpjValidator


@pytest.mark.parametrize(
    "cpf",
    ["52998224725", "11144477735", "00000000191"],
)
def test_cpf_valido(cpf: str) -> None:
    """CPFs com DV correto devem retornar True."""
    pytest.skip("TODO: implementar CpfCnpjValidator.cpf_valido")


@pytest.mark.parametrize(
    "cnpj",
    ["11222333000181", "60746948000112"],
)
def test_cnpj_valido(cnpj: str) -> None:
    """CNPJs com DV correto devem retornar True."""
    pytest.skip("TODO: implementar CpfCnpjValidator.cnpj_valido")


@pytest.mark.parametrize("invalido", ["11111111111", "", "abc"])
def test_cpf_invalido(invalido: str) -> None:
    """CPFs com DV errado devem retornar False."""
    pytest.skip("TODO: implementar CpfCnpjValidator.cpf_valido")
'''


ARQUIVOS["tests/test_plano_contas.py"] = r'''"""Testes da validação contábil do plano de contas."""
from __future__ import annotations

import pytest

from src.domain.models.entities.conta_contabil import ContaContabil
from src.transform.validators.plano_contas import PlanoContasValidator


def _conta(
    codigo: str, pai: str | None, nat: str, grau: int, saldo: str | None = None
) -> ContaContabil:
    return ContaContabil(
        codigo=codigo,
        nome=f"Conta {codigo}",
        codigo_pai=pai,
        natureza=nat,
        grau=grau,
        natureza_saldo=saldo,
    )


def test_plano_valido() -> None:
    """Plano bem formado deve passar."""
    pytest.skip("TODO: implementar PlanoContasValidator.validar")


def test_sintetica_sem_filhos_falha() -> None:
    """Sintética sem filhos deve retornar inválido."""
    pytest.skip("TODO: implementar PlanoContasValidator.validar")


def test_ciclo_falha() -> None:
    """Ciclo A→B→A deve retornar inválido."""
    pytest.skip("TODO: implementar PlanoContasValidator.validar")
'''


# ---------------------------------------------------------------------
#  Configuração do projeto
# ---------------------------------------------------------------------
ARQUIVOS["pyproject.toml"] = r'''[project]
name = "erp-contabil-migracao"
version = "0.1.0"
description = "Módulo de migração do ERP Contábil (Fortes / Tron / SPED)"
requires-python = ">=3.11"

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true
'''


ARQUIVOS[".gitignore"] = r'''# Ambiente virtual
.venv/
venv/
__pycache__/
*.pyc
*.pyo

# Logs do migrador
migracao_erros.log
migracao_quarentena.jsonl

# IDE
.vscode/
.idea/

# Build
build/
dist/
*.egg-info/
'''


# =====================================================================
#  LÓGICA DO SCRIPT
# =====================================================================
def _gerar_init_faltantes(root: Path) -> list[Path]:
    """Garante __init__.py em todos os diretórios de pacote dentro de src/."""
    criados: list[Path] = []
    src = root / "src"
    if not src.exists():
        return criados
    for pasta in [src, *src.rglob("*")]:
        if not pasta.is_dir() or pasta.name == "templates":
            continue
        init = pasta / "__init__.py"
        rel = init.relative_to(root).as_posix()
        if rel in ARQUIVOS:
            continue
        if not init.exists():
            criados.append(init)
    return criados


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Sobrescreve arquivos existentes")
    parser.add_argument("--dry-run", action="store_true", help="Só lista o que faria")
    parser.add_argument("--root", default=".", help="Diretório raiz (default: cwd)")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    print(f"📁 Raiz: {root}\n")

    if not root.is_dir():
        print(f"❌ Diretório não existe: {root}", file=sys.stderr)
        return 1

    criados = pulados = 0
    for rel_path, content in ARQUIVOS.items():
        dest = root / rel_path
        if dest.exists() and not args.force:
            print(f"⏭  {rel_path}")
            pulados += 1
            continue
        if args.dry_run:
            print(f"📝 {rel_path}")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        print(f"✅ {rel_path}")
        criados += 1

    # __init__.py automáticos em qualquer pacote futuro
    for init in _gerar_init_faltantes(root):
        if args.dry_run:
            print(f"📝 {init.relative_to(root).as_posix()}")
        else:
            init.parent.mkdir(parents=True, exist_ok=True)
            init.write_text('"""Pacote gerado automaticamente."""\n', encoding="utf-8")
            print(f"✅ {init.relative_to(root).as_posix()}")
            criados += 1

    print(f"\n📊 {criados} arquivos criados, {pulados} já existiam")
    if args.dry_run:
        print("(modo dry-run — nada foi escrito)")
    else:
        print("\nPróximos passos:")
        print("  1. Procure todos os TODOs:  grep -rn 'TODO: porta do C#' src/")
        print("  2. Implemente arquivo por arquivo, começando por:")
        print("     - src/transform/validators/cpf_cnpj.py      (puro, sem deps)")
        print("     - src/transform/validators/plano_contas.py")
        print("     - src/transform/normalizers/normalizers.py")
        print("     - src/extract/fortes/connection.py")
        print("     - src/extract/fortes/participante_extractor.py")
        print("     - src/load/postgres_bulk_loader.py")
        print("  3. Rodar testes:  pytest -v")
        print("  4. Subir painel:  uvicorn src.web.app:app --reload")
    return 0


if __name__ == "__main__":
    sys.exit(main())