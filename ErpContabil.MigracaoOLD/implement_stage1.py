#!/usr/bin/env python3
"""implement_stage1.py — Aplica fixes + implementações Stage 1.

Este script SOBRESCREVE 17 arquivos do scaffold. Antes de rodar:
    python implement_stage1.py --dry-run        # revisar lista
    python implement_stage1.py --force --backup # aplicar (com backup .bak)

Depois:
    pytest -v              # 8 testes passando (antes: 11 skipped)
    mypy src/              # Success
    ruff check src/        # All checks passed!

Flags:
    --dry-run        Mostra o que faria, sem escrever nada
    --force          Confirma a sobrescrita (obrigatório sem --dry-run)
    --backup         Salva .bak ao lado antes de sobrescrever
    --only {fixes,impl,tests,all}   default: all
    --root DIR       Diretório raiz (default: cwd)
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

# =====================================================================
#  CONTEÚDO DOS ARQUIVOS
# =====================================================================
GRUPO: dict[str, dict[str, str]] = {"fixes": {}, "impl": {}, "tests": {}}


# ---------------------------------------------------------------------
#  GRUPO "fixes" — correções mypy + ruff
# ---------------------------------------------------------------------
GRUPO["fixes"]["src/domain/contracts/transformer.py"] = r'''"""Contrato do motor de transformação (Camada 3)."""
from __future__ import annotations

from typing import Protocol, TypeVar

from src.domain.models.chunk import TransformResult

S = TypeVar("S", contravariant=True)
D = TypeVar("D")


class IEntityTransformer(Protocol[S, D]):
    """Transforma e valida um registro origem → destino.

    Notes:
        `S` é contravariante (só aparece em parâmetro) e `D` invariante
        (aparece em `TransformResult[D]`, que é uma dataclass genérica).
        Sem o `contravariant=True`, mypy strict acusa
        "Invariant type variable S used in protocol where contravariant one is expected".
    """

    def transform(self, origem: S) -> TransformResult[D]:
        """Aplica De-Para, normalizações e validações contábeis.

        Returns:
            TransformResult.ok(destino) se válido, ou
            TransformResult.falha(motivo) — caso em que o registro vai para quarentena.
        """
        ...
'''


GRUPO["fixes"]["src/domain/contracts/extractor.py"] = r'''"""Contrato do motor de extração (Camada 2)."""
from __future__ import annotations

import threading
from collections.abc import Iterator
from typing import Protocol, TypeVar

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


GRUPO["fixes"]["src/domain/contracts/loader.py"] = r'''"""Contrato do motor de inserção de alta performance (Camada 4)."""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeVar

if TYPE_CHECKING:
    import psycopg

T = TypeVar("T")


class IEntityLoader(Protocol[T]):
    """Insere um lote de registros no PostgreSQL local."""

    def load(
        self,
        conn: psycopg.Connection,
        tx: psycopg.Transaction,
        empresa_id: str,
        itens: list[T],
    ) -> int:
        """Executa o INSERT em lote. Retorna quantos registros foram inseridos."""
        ...
'''


GRUPO["fixes"]["src/domain/models/chunk.py"] = r'''"""Modelos de agregação usados pelos motores de ETL."""
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
    def ok(cls, valor: U) -> TransformResult[U]:
        """Cria um resultado de sucesso."""
        return cls(sucesso=True, valor=valor)

    @classmethod
    def falha(cls, motivo: str) -> TransformResult[U]:
        """Cria um resultado de falha (vai para quarentena)."""
        return cls(sucesso=False, motivo=motivo)


@dataclass(frozen=True, slots=True)
class ResultadoValidacaoPlano:
    """Resultado da validação contábil do plano de contas."""

    valido: bool
    erros: list[str] = field(default_factory=list)
'''


GRUPO["fixes"]["src/load/postgres_bulk_loader.py"] = r'''"""Bulk Insert no PostgreSQL via COPY ... FROM STDIN (FORMAT BINARY)."""
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
        conn: psycopg.Connection,
        tx: psycopg.Transaction,
        empresa_id: str,
        itens: list[ParticipanteDestino],
    ) -> int:
        """Executa COPY BINARY. Retorna o número de linhas inseridas."""
        raise NotImplementedError(
            "TODO Stage 2: porta do C# PostgresBinaryBulkLoader.InserirParticipantesAsync"
        )
'''


GRUPO["fixes"]["src/load/postgres_fallback_loader.py"] = r'''"""Fallback linha-a-linha com SAVEPOINT para o caso de COPY falhar."""
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
        conn: psycopg.Connection,
        tx: psycopg.Transaction,
        empresa_id: str,
        itens: list[ParticipanteDestino],
    ) -> int:
        """Retorna quantos registros foram inseridos com sucesso."""
        raise NotImplementedError(
            "TODO Stage 2: porta do C# PostgresFallbackRowLoader"
        )
'''


GRUPO["fixes"]["src/load/sync_outbox_writer.py"] = r'''"""Escritor do Transactional Outbox (padrão Outbox) para o Sincronizador Delta."""
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
        conn: psycopg.Connection,
        tx: psycopg.Transaction,
        entidade: str,
        registro_id: str,
        operacao: OperacaoSync,
    ) -> None:
        """INSERT em sync.sync_outbox (mesma tx do Load)."""
        raise NotImplementedError(
            "TODO Stage 2: porta do C# SyncOutboxWriter.EnfileirarAsync"
        )
'''


GRUPO["fixes"]["src/extract/tron/firebird_extractor.py"] = r'''"""Extrator da base Firebird da Tron Informática."""
from __future__ import annotations

import threading
from collections.abc import Iterator
from dataclasses import dataclass

from src.domain.models.chunk import Chunk


@dataclass(frozen=True, slots=True)
class TronConnectionOptions:
    """Credenciais do Firebird da Tron.

    Ordem dos campos: obrigatórios primeiro, opcionais (com default) depois.
    Python exige essa ordem em dataclasses.
    """

    host: str
    database: str        # caminho do .fdb
    usuario: str
    senha: str
    porta: int = 3050
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
        raise NotImplementedError("TODO Stage 2: porta do C# TronFirebirdExtractor")
        yield  # pragma: no cover
'''


GRUPO["fixes"]["src/domain/enums/enums.py"] = r'''"""Enumerações do domínio de migração."""
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
'''


GRUPO["fixes"]["pyproject.toml"] = r'''[project]
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

# FastAPI/Starlette usam decoradores cujo tipo não é expressável em strict-mode.
# Isolamos o ruído em src/web/ sem afrouxar o resto do projeto.
[[tool.mypy.overrides]]
module = "src.web.*"
disallow_untyped_decorators = false
'''


# ---------------------------------------------------------------------
#  GRUPO "impl" — implementações Stage 1
# ---------------------------------------------------------------------
GRUPO["impl"]["src/transform/validators/cpf_cnpj.py"] = r'''"""Validação de CPF e CNPJ pelo dígito verificador."""
from __future__ import annotations


class CpfCnpjValidator:
    """Algoritmo oficial de validação de CPF/CNPJ (checksum, não só máscara)."""

    @staticmethod
    def somente_digitos(doc: str | None) -> str:
        """Remove tudo que não for dígito. Retorna string vazia se `doc` for None."""
        return "".join(c for c in (doc or "") if c.isdigit())

    @staticmethod
    def cpf_valido(cpf: str) -> bool:
        """Verifica os dois dígitos verificadores do CPF.

        Notes:
            - Rejeita strings com menos/mais de 11 dígitos, não-numéricas,
              ou com todos os dígitos iguais (ex.: 11111111111).
        """
        if not cpf.isdigit() or len(cpf) != 11 or len(set(cpf)) == 1:
            return False

        # 1º dígito: pesos 10..2 sobre os 9 primeiros dígitos
        soma = sum((ord(cpf[i]) - 48) * (10 - i) for i in range(9))
        resto = soma % 11
        dv1 = 0 if resto < 2 else 11 - resto
        if (ord(cpf[9]) - 48) != dv1:
            return False

        # 2º dígito: pesos 11..2 sobre os 10 primeiros dígitos
        soma = sum((ord(cpf[i]) - 48) * (11 - i) for i in range(10))
        resto = soma % 11
        dv2 = 0 if resto < 2 else 11 - resto
        return (ord(cpf[10]) - 48) == dv2

    @staticmethod
    def cnpj_valido(cnpj: str) -> bool:
        """Verifica os dois dígitos verificadores do CNPJ."""
        if not cnpj.isdigit() or len(cnpj) != 14 or len(set(cnpj)) == 1:
            return False

        pesos1 = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
        pesos2 = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)

        soma = sum((ord(cnpj[i]) - 48) * pesos1[i] for i in range(12))
        resto = soma % 11
        dv1 = 0 if resto < 2 else 11 - resto
        if (ord(cnpj[12]) - 48) != dv1:
            return False

        soma = sum((ord(cnpj[i]) - 48) * pesos2[i] for i in range(13))
        resto = soma % 11
        dv2 = 0 if resto < 2 else 11 - resto
        return (ord(cnpj[13]) - 48) == dv2

    @classmethod
    def validar(cls, doc: str | None, tipo_pessoa: str) -> tuple[bool, str | None]:
        """Valida e retorna (ok, motivo_rejeicao).

        Args:
            doc: documento com ou sem máscara (só os dígitos são usados).
            tipo_pessoa: "FISICA" ou "JURIDICA".

        Returns:
            (True, None) se válido; (False, motivo) caso contrário.
        """
        d = cls.somente_digitos(doc)
        if not d:
            return False, "Documento vazio"

        if tipo_pessoa == "FISICA":
            if not cls.cpf_valido(d):
                return False, "CPF com dígito verificador inválido"
            return True, None

        if not cls.cnpj_valido(d):
            return False, "CNPJ com dígito verificador inválido"
        return True, None
'''


GRUPO["impl"]["src/transform/validators/plano_contas.py"] = r'''"""Validação contábil do plano de contas."""
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
        erros: list[str] = []
        if not contas:
            return ResultadoValidacaoPlano(valido=False, erros=["Plano de contas vazio."])

        por_codigo: dict[str, ContaContabil] = {c.codigo: c for c in contas}

        # índice de filhos (para checar se sintética/analítica está no nível certo)
        filhos: dict[str, list[ContaContabil]] = {}
        for c in contas:
            if c.codigo_pai is not None:
                filhos.setdefault(c.codigo_pai, []).append(c)

        # checagens linha-a-linha
        for conta in contas:
            if conta.codigo_pai is not None:
                pai = por_codigo.get(conta.codigo_pai)
                if pai is None:
                    erros.append(
                        f"Conta {conta.codigo}: pai '{conta.codigo_pai}' inexistente."
                    )
                elif conta.grau != pai.grau + 1:
                    erros.append(
                        f"Conta {conta.codigo}: grau {conta.grau} != "
                        f"grau do pai ({pai.grau}) + 1."
                    )

            tem_filhos = conta.codigo in filhos and len(filhos[conta.codigo]) > 0

            if conta.natureza == "SINTETICA" and not tem_filhos:
                erros.append(
                    f"Conta sintética {conta.codigo} não possui contas filhas."
                )

            if conta.natureza == "ANALITICA":
                if tem_filhos:
                    erros.append(
                        f"Conta analítica {conta.codigo} possui filhas — "
                        f"deve ser sintética."
                    )
                if not conta.natureza_saldo or not conta.natureza_saldo.strip():
                    erros.append(
                        f"Conta analítica {conta.codigo} sem natureza de saldo (D/C)."
                    )

            if conta.natureza not in ("SINTETICA", "ANALITICA"):
                erros.append(
                    f"Conta {conta.codigo}: natureza '{conta.natureza}' inválida."
                )

        # detecção de ciclo
        for conta in contas:
            visitados: set[str] = set()
            atual = conta
            while (
                atual.codigo_pai is not None
                and atual.codigo_pai in por_codigo
            ):
                if atual.codigo in visitados:
                    erros.append(
                        f"Ciclo detectado no plano de contas a partir de {conta.codigo}."
                    )
                    break
                visitados.add(atual.codigo)
                atual = por_codigo[atual.codigo_pai]

        return ResultadoValidacaoPlano(valido=not erros, erros=erros)
'''


GRUPO["impl"]["src/transform/normalizers/normalizers.py"] = r'''"""Normalizações de texto, documento, UF, e-mail e telefone."""
from __future__ import annotations

UFS_IBGE: frozenset[str] = frozenset({
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
})


class Normalizers:
    """Funções puras de normalização de campos.

    Notes:
        - Todas as funções retornam `None` quando o valor de entrada é vazio,
          para facilitar o INSERT como NULL no PostgreSQL.
        - Nenhuma função lança exceção: entradas inválidas viram `None`.
    """

    @staticmethod
    def texto(v: str | None) -> str | None:
        """Trim, colapsa espaços internos, retorna None se vazio."""
        if v is None:
            return None
        limpo = " ".join(v.strip().split())
        return limpo or None

    @staticmethod
    def documento(v: str | None) -> str | None:
        """Mantém só dígitos."""
        if v is None:
            return None
        d = "".join(c for c in v if c.isdigit())
        return d or None

    @staticmethod
    def uf(v: str | None) -> str | None:
        """Uppercase e valida contra a lista de UFs do IBGE."""
        if v is None:
            return None
        uf = v.strip().upper()
        return uf if uf in UFS_IBGE else None

    @staticmethod
    def email(v: str | None) -> str | None:
        """Lowercase e trim. Retorna None se não contiver '@'."""
        if v is None:
            return None
        e = v.strip().lower()
        return e if "@" in e else None

    @staticmethod
    def telefone(v: str | None) -> str | None:
        """Mantém só dígitos. Retorna None se tiver menos de 10 dígitos."""
        if v is None:
            return None
        d = "".join(c for c in v if c.isdigit())
        return d if len(d) >= 10 else None
'''


GRUPO["impl"]["src/transform/mappings/fortes_para_erp_map.py"] = r'''"""Dicionário De-Para Fortes → ERP."""
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
        if origem is None:
            return "JURIDICA"
        v = origem.strip().upper()
        if v in ("F", "FISICA", "PF"):
            return "FISICA"
        return "JURIDICA"
'''


GRUPO["impl"]["src/extract/fortes/connection.py"] = r'''"""Fábrica de conexão com o SQL Server da Fortes Tecnologia."""
from __future__ import annotations

import contextlib
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pymssql

from src.domain.models.migration_options import FortesConnectionOptions


class FortesConnectionFactory:
    """Cria conexões curtas e identificáveis com o SQL Server da Fortes.

    Notes:
        - NÃO abrir um pool grande: o banco é do cliente. Abrir/fechar por chunk
          evita travar o ERP enquanto ele trabalha.
        - `appname` permite ao DBA identificar as sessões do migrador
          (SELECT * FROM sys.dm_exec_sessions WHERE program_name LIKE 'ERPContabil%').
        - `pymssql` (FreeTDS) é pure-Python + client nativo, mas NÃO usa string
          de conexão estilo ADO.NET; usamos kwargs. Se o servidor exigir
          `TrustServerCertificate`, instale `pyodbc` + ODBC Driver 18 e troque
          esta fábrica (interface se mantém).
    """

    def __init__(self, opt: FortesConnectionOptions) -> None:
        self._opt = opt

    def build_kwargs(self) -> dict[str, Any]:
        """Monta kwargs aceitos por `pymssql.connect(**kwargs)`."""
        return {
            "server": self._opt.host,
            "port": str(self._opt.porta),
            "user": self._opt.usuario,
            "password": self._opt.senha,
            "database": self._opt.database,
            "timeout": self._opt.timeout_conexao_s,
            "login_timeout": self._opt.timeout_conexao_s,
            "charset": "UTF-8",
            "appname": "ERPContabil-Migrador-Fortes",
        }

    def build_connection_string(self) -> str:
        """Representação legível para log — senha mascarada, não abre conexão."""
        return (
            f"mssql://{self._opt.usuario}:***@"
            f"{self._opt.host}:{self._opt.porta}/{self._opt.database}"
        )

    @contextlib.contextmanager
    def open(self) -> Iterator[pymssql.Connection]:
        """Abre a conexão e garante fechamento ao sair do bloco `with`."""
        import pymssql  # import tardio: só carrega FreeTDS quando precisa conectar

        conn = pymssql.connect(**self.build_kwargs())
        try:
            yield conn
        finally:
            conn.close()
'''


# ---------------------------------------------------------------------
#  GRUPO "tests" — testes com assertions reais
# ---------------------------------------------------------------------
GRUPO["tests"]["tests/test_cpf_cnpj.py"] = r'''"""Testes de validação de CPF/CNPJ."""
from __future__ import annotations

import pytest

from src.transform.validators.cpf_cnpj import CpfCnpjValidator


@pytest.mark.parametrize(
    "cpf",
    ["52998224725", "11144477735", "00000000191"],
)
def test_cpf_valido(cpf: str) -> None:
    """CPFs com DV correto devem retornar True."""
    assert CpfCnpjValidator.cpf_valido(cpf) is True


@pytest.mark.parametrize(
    "cnpj",
    ["11222333000181", "60746948000112"],
)
def test_cnpj_valido(cnpj: str) -> None:
    """CNPJs com DV correto devem retornar True."""
    assert CpfCnpjValidator.cnpj_valido(cnpj) is True


@pytest.mark.parametrize("invalido", ["11111111111", "", "abc"])
def test_cpf_invalido(invalido: str) -> None:
    """CPFs com DV errado ou formato inválido devem retornar False."""
    assert CpfCnpjValidator.cpf_valido(invalido) is False


@pytest.mark.parametrize("invalido", ["00000000000000", "", "xyz"])
def test_cnpj_invalido(invalido: str) -> None:
    """CNPJs com DV errado ou formato inválido devem retornar False."""
    assert CpfCnpjValidator.cnpj_valido(invalido) is False


def test_somente_digitos() -> None:
    """Máscaras devem ser removidas."""
    assert CpfCnpjValidator.somente_digitos("529.982.247-25") == "52998224725"
    assert CpfCnpjValidator.somente_digitos("11.222.333/0001-81") == "11222333000181"
    assert CpfCnpjValidator.somente_digitos(None) == ""
    assert CpfCnpjValidator.somente_digitos("abc") == ""


def test_validar_alto_nivel() -> None:
    """`validar()` deve retornar (ok, motivo)."""
    ok, motivo = CpfCnpjValidator.validar("529.982.247-25", "FISICA")
    assert ok is True
    assert motivo is None

    ok, motivo = CpfCnpjValidator.validar("11.222.333/0001-81", "JURIDICA")
    assert ok is True
    assert motivo is None

    ok, motivo = CpfCnpjValidator.validar("", "FISICA")
    assert ok is False
    assert motivo == "Documento vazio"

    ok, motivo = CpfCnpjValidator.validar("12345678901", "FISICA")
    assert ok is False
    assert motivo is not None and "CPF" in motivo
'''


GRUPO["tests"]["tests/test_plano_contas.py"] = r'''"""Testes da validação contábil do plano de contas."""
from __future__ import annotations

from src.domain.models.entities.conta_contabil import ContaContabil
from src.transform.validators.plano_contas import PlanoContasValidator


def _conta(
    codigo: str,
    pai: str | None,
    nat: str,
    grau: int,
    saldo: str | None = None,
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
    """Plano bem formado (sintética → analítica) deve passar."""
    contas = [
        _conta("1", None, "SINTETICA", 1),
        _conta("1.1", "1", "ANALITICA", 2, "DEVEDORA"),
    ]
    resultado = PlanoContasValidator.validar(contas)
    assert resultado.valido is True
    assert resultado.erros == []


def test_sintetica_sem_filhos_falha() -> None:
    """Sintética sem filhos deve retornar inválido."""
    contas = [_conta("1", None, "SINTETICA", 1)]
    resultado = PlanoContasValidator.validar(contas)
    assert resultado.valido is False
    assert any("sint" in e.lower() for e in resultado.erros)


def test_ciclo_falha() -> None:
    """Ciclo A→B→A deve retornar inválido."""
    contas = [
        _conta("1", "2", "SINTETICA", 2),
        _conta("2", "1", "SINTETICA", 2),
    ]
    resultado = PlanoContasValidator.validar(contas)
    assert resultado.valido is False
    assert any("ciclo" in e.lower() for e in resultado.erros)


def test_pai_inexistente_falha() -> None:
    """Codigo_pai que não existe na lista deve ser reportado."""
    contas = [_conta("1.1", "9.9", "ANALITICA", 2, "DEVEDORA")]
    resultado = PlanoContasValidator.validar(contas)
    assert resultado.valido is False
    assert any("inexistente" in e.lower() for e in resultado.erros)


def test_analitica_sem_natureza_saldo_falha() -> None:
    """Analítica sem natureza de saldo deve falhar."""
    contas = [
        _conta("1", None, "SINTETICA", 1),
        _conta("1.1", "1", "ANALITICA", 2),   # sem saldo
    ]
    resultado = PlanoContasValidator.validar(contas)
    assert resultado.valido is False
    assert any("saldo" in e.lower() for e in resultado.erros)
'''


# =====================================================================
#  EXECUÇÃO
# =====================================================================
def _aplicar(
    root: Path,
    grupo: str,
    force: bool,
    backup: bool,
    dry_run: bool,
) -> tuple[int, int, int]:
    criados = atualizados = pulados = 0
    for rel, content in GRUPO[grupo].items():
        dest = root / rel
        prefixo = {"fixes": "🔧", "impl": "⚙️ ", "tests": "🧪"}[grupo]

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
            print(f"{prefixo} [SKIP]      {rel}  (já existe; use --force)")
            pulados += 1
            continue

        if dry_run:
            print(f"{prefixo} [OVERWRITE] {rel}")
            atualizados += 1
            continue

        if backup:
            bkp = dest.with_suffix(dest.suffix + ".bak")
            shutil.copy2(dest, bkp)
        dest.write_text(content, encoding="utf-8")
        print(f"{prefixo} [UPDATED]   {rel}")
        atualizados += 1

    return criados, atualizados, pulados


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--only", choices=["fixes", "impl", "tests", "all"], default="all")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"❌ Raiz inválida: {root}", file=sys.stderr)
        return 1

    if not args.force and not args.dry_run:
        print("⚠️  Este script SOBRESCREVE arquivos existentes.")
        print("    Use --dry-run para revisar, ou --force --backup para aplicar.\n")
        return 2

    print(f"📁 Raiz: {root}")
    print(f"🎯 Grupos: {args.only}")
    print(f"🛡️  Backup: {'SIM' if args.backup else 'não'}\n")

    grupos = ["fixes", "impl", "tests"] if args.only == "all" else [args.only]
    total_criados = total_atualizados = total_pulados = 0

    for grupo in grupos:
        print(f"\n── {grupo.upper()} ──")
        c, a, p = _aplicar(root, grupo, args.force, args.backup, args.dry_run)
        total_criados += c
        total_atualizados += a
        total_pulados += p

    print(f"\n📊 Criados: {total_criados}, Atualizados: {total_atualizados}, "
          f"Pulados: {total_pulados}")

    if args.dry_run:
        print("(dry-run — nada foi escrito)")
        return 0

    print("\nPróximos passos:")
    print("  python -m compileall -q src tests   && echo '✅ sintaxe OK'")
    print("  pytest -v                          # 14+ testes devem passar")
    print("  mypy src/                          # 'Success: no issues found'")
    print("  ruff check src/                    # 'All checks passed!'")
    return 0


if __name__ == "__main__":
    sys.exit(main())