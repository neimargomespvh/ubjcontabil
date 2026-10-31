#!/usr/bin/env python3
"""fix_stage2.py — Corrige mypy/ruff do Stage 2 + cria setup_db.py.

Aplica:
  fixes   → 5 arquivos corrigidos
  db      → scripts/setup_db.py (cria banco + aplica DDL via psycopg)

Uso:
    python fix_stage2.py --dry-run
    python fix_stage2.py --force --backup

Depois:
    # Opção A — instalar postgres nativo:
    sudo apt install postgresql postgresql-contrib
    sudo systemctl start postgresql
    sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'postgres';"

    # Opção B — Docker:
    docker run -d --name erp-pg -e POSTGRES_PASSWORD=postgres \\
        -p 5432:5432 postgres:16

    # Criar schema:
    python scripts/setup_db.py

    # Verificação final:
    pytest -q && mypy src/ && ruff check src/
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

GRUPO: dict[str, dict[str, str]] = {"fixes": {}, "db": {}}


# ---------------------------------------------------------------------
#  FIX 1 — extractor: `_mapear(r: Any)` + SIM117
# ---------------------------------------------------------------------
GRUPO["fixes"]["src/extract/fortes/participante_extractor.py"] = r'''"""Extrator de participantes (clientes/fornecedores) da Fortes."""
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
            with (
                self._factory.open() as conn,
                conn.cursor() as cur,
            ):
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
    def _mapear(r: Any) -> ParticipanteOrigem:
        """Converte uma linha do pymssql para o modelo de domínio.

        Notes:
            `r` é `Any` porque o `DictRow` do pymssql tem `__getitem__`
            tipado como uma união larga (`str | int | ... | None`). Como esta
            é a fronteira do sistema (row externa → modelo), `Any` é honesto.
        """
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


# ---------------------------------------------------------------------
#  FIX 2 — orchestrator: Sequence[object] + SIM117 + import no topo
# ---------------------------------------------------------------------
GRUPO["fixes"]["src/infrastructure/orchestrator.py"] = r'''"""Orquestrador: Extract → Transform → Load + Outbox (pipeline FORTES)."""
from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Sequence

import psycopg

from src.domain.contracts.orchestrator import IMigrationOrchestrator
from src.domain.enums.enums import OperacaoSync, StatusMigracao
from src.domain.models.entities.participante import ParticipanteOrigem
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
        itens: Sequence[object],
        empresa_id: str,
        result: MigrationResult,
    ) -> None:
        """Transforma → valida → carrega um lote (uma transação por chunk).

        Notes:
            `Sequence[object]` (não `list[object]`) porque `list` é invariante
            em meu mypy strict — só `Sequence` aceita `list[ParticipanteOrigem]`.
        """
        validos: list = []
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
#  FIX 3 — logger: datetime.UTC + SIM117 (dentro de try → manual)
# ---------------------------------------------------------------------
GRUPO["fixes"]["src/infrastructure/logging/migration_logger.py"] = r'''"""Logger resiliente (JSONL + tabela migracao.erro)."""
from __future__ import annotations

import json
import socket
import threading
from datetime import UTC, datetime
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
            "ts": datetime.now(UTC).isoformat(),
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
            "ts": datetime.now(UTC).isoformat(),
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
            with (
                psycopg.connect(self._connection_string, autocommit=True) as conn,
                conn.cursor() as cur,
            ):
                cur.execute(sql, params)
        except Exception:
            pass  # arquivo já tem o registro — auditoria preservada
'''


# ---------------------------------------------------------------------
#  FIX 4 — bulk loader: remove `import psycopg` + SIM117
# ---------------------------------------------------------------------
GRUPO["fixes"]["src/load/postgres_bulk_loader.py"] = r'''"""Bulk Insert no PostgreSQL via COPY ... FROM STDIN (FORMAT BINARY)."""
from __future__ import annotations

from typing import TYPE_CHECKING

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
        with conn.cursor() as cur, cur.copy(_COPY_SQL) as copy:
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


# ---------------------------------------------------------------------
#  FIX 5 — fallback loader: SIM117 (dentro de try → manual)
# ---------------------------------------------------------------------
GRUPO["fixes"]["src/load/postgres_fallback_loader.py"] = r'''"""Fallback linha-a-linha com SAVEPOINT."""
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
                # `conn.transaction()` vira SAVEPOINT se já houver tx aberta.
                with conn.transaction(), conn.cursor() as cur:
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


# ---------------------------------------------------------------------
#  DB — setup_db.py (sem psql)
# ---------------------------------------------------------------------
GRUPO["db"]["scripts/setup_db.py"] = r'''#!/usr/bin/env python3
"""setup_db.py — Cria o banco `erp_contabil` e aplica `ddl/schema.sql`.

Não precisa de `psql` instalado — usa o próprio psycopg.

Uso:
    # Verifica a conexão e mostra o que faria:
    python scripts/setup_db.py --dry-run

    # Aplica:
    python scripts/setup_db.py

    # Customizar credenciais:
    DATABASE_URL="postgresql://user:senha@host:5432/postgres" \\
        python scripts/setup_db.py

Pré-requisitos:
    - PostgreSQL rodando em localhost:5432 (nativo ou Docker)
    - Usuário com permissão para CREATE DATABASE
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg

DEFAULT_ADMIN_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres"
)
APP_DB = os.environ.get("APP_DB", "erp_contabil")


def _admin_url_without_db(url: str) -> str:
    """Troca o path final por /postgres (banco administrativo)."""
    base, _, _ = url.rpartition("/")
    return f"{base}/postgres"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--db", default=APP_DB, help="Nome do banco a criar")
    parser.add_argument(
        "--ddl", default="ddl/schema.sql", help="Caminho do DDL a aplicar"
    )
    args = parser.parse_args()

    ddl_path = Path(args.ddl)
    if not ddl_path.exists():
        print(f"❌ DDL não encontrado: {ddl_path}", file=sys.stderr)
        return 1

    admin_url = _admin_url_without_db(DEFAULT_ADMIN_URL)
    app_url = DEFAULT_ADMIN_URL.rpartition("/")[0] + f"/{args.db}"

    print(f"🔌 Admin:  {admin_url}")
    print(f"🔌 App:    {app_url}")
    print(f"🗄️  DDL:    {ddl_path}")

    if args.dry_run:
        print("\n(dry-run — nada foi executado)")
        return 0

    # 1. Garante que o banco existe
    try:
        with psycopg.connect(admin_url, autocommit=True) as conn:
            existe = conn.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (args.db,)
            ).fetchone()
            if not existe:
                conn.execute(f'CREATE DATABASE "{args.db}"')
                print(f"✅ Banco '{args.db}' criado")
            else:
                print(f"⏭  Banco '{args.db}' já existe")
    except psycopg.OperationalError as e:
        print(f"\n❌ Erro de conexão: {e}", file=sys.stderr)
        print("\nInstale e inicie o PostgreSQL:", file=sys.stderr)
        print("  sudo apt install postgresql postgresql-contrib", file=sys.stderr)
        print("  sudo systemctl start postgresql", file=sys.stderr)
        print("  sudo -u postgres psql -c \"ALTER USER postgres PASSWORD 'postgres';\"",
              file=sys.stderr)
        print("\nOu use Docker:", file=sys.stderr)
        print("  docker run -d --name erp-pg -e POSTGRES_PASSWORD=postgres \\",
              file=sys.stderr)
        print("      -p 5432:5432 postgres:16", file=sys.stderr)
        return 1

    # 2. Aplica o DDL
    try:
        with psycopg.connect(app_url) as conn, conn.cursor() as cur:
            cur.execute(ddl_path.read_text(encoding="utf-8"))
            conn.commit()
        print(f"✅ DDL aplicado em '{args.db}'")
    except psycopg.Error as e:
        print(f"❌ Erro ao aplicar DDL: {e}", file=sys.stderr)
        return 1

    print("\n✓ Pronto. Connection string do app:")
    print(f"  {app_url.replace(':postgres@', ':***@')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


# =====================================================================
#  EXECUÇÃO
# =====================================================================
def _aplicar(
    root: Path, grupo: str, force: bool, backup: bool, dry_run: bool
) -> tuple[int, int, int]:
    criados = atualizados = pulados = 0
    for rel, content in GRUPO[grupo].items():
        dest = root / rel
        prefixo = {"fixes": "🔧", "db": "🗄️ "}[grupo]
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
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--only", choices=["fixes", "db", "all"], default="all")
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
    grupos = ["fixes", "db"] if args.only == "all" else [args.only]
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
    print("  1. Instale/inicie o PostgreSQL (se ainda não fez):")
    print("     sudo apt install postgresql postgresql-contrib")
    print("     sudo systemctl start postgresql")
    print("     sudo -u postgres psql -c \"ALTER USER postgres PASSWORD 'postgres';\"")
    print("  2. Crie o schema:")
    print("     python scripts/setup_db.py")
    print("  3. Verificação final:")
    print("     pytest -q && mypy src/ && ruff check src/")
    return 0


if __name__ == "__main__":
    sys.exit(main())