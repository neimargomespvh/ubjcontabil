#!/usr/bin/env python3
"""implement_stage4.py — Sync Delta + SPED estruturado + Tron config + Auth.

Uso:
    python implement_stage4.py --dry-run
    python implement_stage4.py --force --backup

Depois:
    pip install -r requirements-stage4.txt
    psql -d erp_contabil -f ddl/schema_stage4.sql
    export ADMIN_PASSWORD=...   # ou defina no .env
    ./scripts/run_admin.sh      # painel protegido por HTTP Basic
    python scripts/run_sync_worker.py   # worker delta (processo separado)
    pytest -v && mypy src/ && ruff check src/
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

G: dict[str, dict[str, str]] = {
    "ddl": {}, "tron": {}, "sped": {}, "sync": {},
    "load": {}, "orchestrator": {}, "web": {},
    "scripts": {}, "tests": {}, "config": {},
}


# =====================================================================
#  DDL
# =====================================================================
G["ddl"]["ddl/schema_stage4.sql"] = r'''-- =========================================================
-- Stage 4 — Sync delta (empresa_id + DLQ)
-- Rodar:  psql -d erp_contabil -f ddl/schema_stage4.sql
-- =========================================================

ALTER TABLE sync.sync_outbox
    ADD COLUMN IF NOT EXISTS empresa_id TEXT;

UPDATE sync.sync_outbox SET empresa_id = 'legacy' WHERE empresa_id IS NULL;
ALTER TABLE sync.sync_outbox ALTER COLUMN empresa_id SET NOT NULL;

-- Unicidade: um evento pendente por (empresa, entidade, registro)
CREATE UNIQUE INDEX IF NOT EXISTS uq_outbox_pendente
    ON sync.sync_outbox (empresa_id, entidade, registro_id)
    WHERE sincronizado_em IS NULL;

-- Dead Letter Queue: eventos que esgotaram tentativas
CREATE TABLE IF NOT EXISTS sync.sync_dlq (
    id            UUID PRIMARY KEY,
    empresa_id    TEXT NOT NULL,
    entidade      TEXT NOT NULL,
    operacao      TEXT NOT NULL,
    registro_id   TEXT NOT NULL,
    tentativas    INT NOT NULL,
    erro          TEXT,
    criado_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
    movido_em     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_dlq_entidade ON sync.sync_dlq (entidade, movido_em);
'''


# =====================================================================
#  TRON
# =====================================================================
G["tron"]["configs/tron_map.example.json"] = r'''{
  "_comentario": "Exemplo de De-Para para a Tron. Rode TronSchemaDiscovery primeiro e ajuste os nomes reais. Formato: {coluna_origem: coluna_destino_ou_valor_literal}.",
  "entidades": {
    "participante": {
      "tabela": "CLIENTES",
      "campo_chave": "CODIGO",
      "mapa": {
        "CODIGO": "codigo_origem",
        "NOME": "razao_social",
        "FANTASIA": "nome_fantasia",
        "CNPJ": "documento_cnpj",
        "CPF": "documento_cpf",
        "INSCR_EST": "inscricao_estadual",
        "CIDADE": "municipio",
        "UF": "uf",
        "CEP": "cep",
        "EMAIL": "email",
        "FONE": "telefone",
        "TIPO": "tipo_pessoa_literal"
      }
    },
    "conta_contabil": {
      "tabela": "PLANO_CONTAS",
      "campo_chave": "CODIGO",
      "mapa": {
        "CODIGO": "codigo",
        "DESCRICAO": "nome",
        "COD_PAI": "codigo_pai",
        "TIPO": "natureza_literal",
        "NIVEL": "grau",
        "NATUREZA": "natureza_saldo"
      }
    }
  }
}
'''


G["tron"]["src/extract/tron/schema_discovery.py"] = r'''"""Descoberta de schema do Firebird da Tron (cache em JSON)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.extract.tron.firebird_extractor import TronConnectionOptions


@dataclass(frozen=True, slots=True)
class TronColuna:
    tabela: str
    coluna: str
    tipo: str
    tamanho: int | None
    nulavel: bool


class TronSchemaDiscovery:
    """Lê INFORMATION_SCHEMA do Firebird e salva um snapshot em JSON.

    Uso típico (primeira execução contra um cliente novo):
        disc = TronSchemaDiscovery(opt)
        disc.salvar_snapshot(Path("configs/tron_schema_real.json"))

    Depois, use o JSON como referência para preencher `tron_map.json`.
    """

    _SQL = """
        SELECT TRIM(r.RDB$RELATION_NAME)  AS tabela,
               TRIM(f.RDB$FIELD_NAME)    AS coluna,
               CASE f.RDB$FIELD_TYPE
                    WHEN 7  THEN 'SMALLINT'
                    WHEN 8  THEN 'INTEGER'
                    WHEN 12 THEN 'DATE'
                    WHEN 13 THEN 'TIME'
                    WHEN 16 THEN 'BIGINT'
                    WHEN 27 THEN 'DOUBLE'
                    WHEN 35 THEN 'TIMESTAMP'
                    WHEN 37 THEN 'VARCHAR'
                    WHEN 261 THEN 'BLOB'
                    ELSE 'OUTRO'
               END AS tipo,
               f.RDB$CHARACTER_LENGTH AS tamanho,
               CASE WHEN f.RDB$NULL_FLAG = 1 THEN 0 ELSE 1 END AS nulavel
        FROM RDB$RELATION_FIELDS f
        JOIN RDB$RELATIONS r ON r.RDB$RELATION_NAME = f.RDB$RELATION_NAME
        WHERE r.RDB$SYSTEM_FLAG = 0
        ORDER BY r.RDB$RELATION_NAME, f.RDB$FIELD_POSITION
    """

    def __init__(self, opt: TronConnectionOptions) -> None:
        self._opt = opt

    def descobrir(self) -> list[TronColuna]:
        from firebird.driver import connect

        dsn = f"{self._opt.host}/{self._opt.porta}:{self._opt.database}"
        conn = connect(
            dsn, user=self._opt.usuario, password=self._opt.senha,
            charset=self._opt.charset,
        )
        try:
            cur = conn.cursor()
            cur.execute(self._SQL)
            return [
                TronColuna(
                    tabela=str(r[0]).strip(),
                    coluna=str(r[1]).strip(),
                    tipo=str(r[2]),
                    tamanho=int(r[3]) if r[3] is not None else None,
                    nulavel=bool(r[4]),
                )
                for r in cur.fetchall()
            ]
        finally:
            conn.close()

    def salvar_snapshot(self, destino: Path) -> int:
        """Serializa o schema em JSON. Retorna o número de colunas."""
        colunas = self.descobrir()
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(
            json.dumps([asdict(c) for c in colunas], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return len(colunas)


def carregar_snapshot(caminho: Path) -> dict[str, list[TronColuna]]:
    """Carrega o snapshot e agrupa por tabela."""
    dados: list[dict[str, Any]] = json.loads(caminho.read_text(encoding="utf-8"))
    por_tabela: dict[str, list[TronColuna]] = {}
    for d in dados:
        por_tabela.setdefault(d["tabela"], []).append(TronColuna(**d))
    return por_tabela
'''


G["tron"]["src/extract/tron/tron_extractor.py"] = r'''"""Extrator genérico da Tron (Firebird), dirigido por arquivo de De-Para."""
from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.domain.models.chunk import Chunk
from src.domain.models.entities.conta_contabil import ContaContabil
from src.domain.models.entities.participante import ParticipanteOrigem
from src.extract.tron.firebird_extractor import TronConnectionOptions
from src.transform.normalizers.normalizers import Normalizers


@dataclass(frozen=True, slots=True)
class TronEntityConfig:
    """De-Para de uma entidade da Tron."""

    tabela: str
    campo_chave: str
    mapa: dict[str, str]


@dataclass(frozen=True, slots=True)
class TronConfig:
    entidades: dict[str, TronEntityConfig]

    @classmethod
    def from_file(cls, caminho: Path) -> TronConfig:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        return cls({
            nome: TronEntityConfig(
                tabela=cfg["tabela"],
                campo_chave=cfg["campo_chave"],
                mapa=cfg["mapa"],
            )
            for nome, cfg in dados["entidades"].items()
        })


class TronExtractor:
    """Extrai registros da Tron usando um TronConfig.

    Notas:
        - A chave primária da tabela deve ser monotônica para keyset pagination.
        - O mapa De-Para converte colunas da Tron → campos do nosso domínio.
        - Sufixo `_literal` indica que o valor vem direto do campo (ex.: "S"/"A"
          vira "SINTETICA"/"ANALITICA" via função de normalização).
    """

    def __init__(
        self,
        opt: TronConnectionOptions,
        config: TronConfig,
        tamanho_chunk: int = 5_000,
    ) -> None:
        self._opt = opt
        self._config = config
        self._tamanho_chunk = tamanho_chunk

    def _conectar(self) -> Any:
        from firebird.driver import connect

        dsn = f"{self._opt.host}/{self._opt.porta}:{self._opt.database}"
        return connect(
            dsn, user=self._opt.usuario, password=self._opt.senha,
            charset=self._opt.charset,
        )

    def _iterar(
        self, entidade: str, stop_event: threading.Event | None = None
    ) -> Iterator[tuple[dict[str, Any], int]]:
        cfg = self._config.entidades[entidade]
        colunas = ", ".join(cfg.mapa.keys())
        sql = (
            f"SELECT {colunas} FROM {cfg.tabela} "
            f"WHERE {cfg.campo_chave} > ? "
            f"ORDER BY {cfg.campo_chave}"
        )
        ultimo = 0
        conn = self._conectar()
        try:
            cur = conn.cursor()
            while True:
                if stop_event is not None and stop_event.is_set():
                    return
                cur.execute(sql, (ultimo,))
                rows = cur.fetchmany(self._tamanho_chunk)
                if not rows:
                    return
                for row in rows:
                    yield dict(zip(cfg.mapa.keys(), row, strict=True)), ultimo
                ultimo = int(rows[-1][list(cfg.mapa.keys()).index(cfg.campo_chave)])
                if len(rows) < self._tamanho_chunk:
                    return
        finally:
            conn.close()

    # -- públicas ------------------------------------------------------
    def extract_participantes(
        self, stop_event: threading.Event | None = None
    ) -> Iterator[Chunk[ParticipanteOrigem]]:
        lote: list[ParticipanteOrigem] = []
        total = 0
        for row, _ in self._iterar("participante", stop_event):
            lote.append(self._mapear_participante(row))
            total += 1
            if len(lote) >= self._tamanho_chunk:
                yield Chunk(itens=lote, total_acumulado=total)
                lote = []
        if lote:
            yield Chunk(itens=lote, total_acumulado=total)

    def extract_contas(
        self, stop_event: threading.Event | None = None
    ) -> Iterator[Chunk[ContaContabil]]:
        lote: list[ContaContabil] = []
        total = 0
        for row, _ in self._iterar("conta_contabil", stop_event):
            lote.append(self._mapear_conta(row))
            total += 1
            if len(lote) >= self._tamanho_chunk:
                yield Chunk(itens=lote, total_acumulado=total)
                lote = []
        if lote:
            yield Chunk(itens=lote, total_acumulado=total)

    # -- mappers ------------------------------------------------------
    @staticmethod
    def _mapear_participante(row: dict[str, Any]) -> ParticipanteOrigem:
        cnpj = Normalizers.documento(str(row.get("CNPJ") or ""))
        cpf = Normalizers.documento(str(row.get("CPF") or ""))
        tipo_lit = str(row.get("TIPO") or "").strip().upper()
        tipo = "FISICA" if tipo_lit in ("F", "PF", "FISICA") else "JURIDICA"
        return ParticipanteOrigem(
            codigo_origem=int(row["CODIGO"]),
            razao_social=row.get("NOME"),
            nome_fantasia=row.get("FANTASIA"),
            documento=cnpj or cpf or None,
            inscricao_estadual=row.get("INSCR_EST"),
            inscricao_municipal=None,
            endereco=None,
            cidade=row.get("CIDADE"),
            uf=row.get("UF"),
            cep=row.get("CEP"),
            email=row.get("EMAIL"),
            telefone=row.get("FONE"),
            tipo_pessoa=tipo,
        )

    @staticmethod
    def _mapear_conta(row: dict[str, Any]) -> ContaContabil:
        tipo = str(row.get("TIPO") or "").strip().upper()
        natureza = "SINTETICA" if tipo in ("S", "01", "1") else "ANALITICA"
        return ContaContabil(
            codigo=str(row["CODIGO"]),
            nome=str(row.get("DESCRICAO") or "(sem nome)"),
            codigo_pai=str(row.get("COD_PAI")) if row.get("COD_PAI") else None,
            natureza=natureza,
            grau=int(row.get("NIVEL") or 1),
            natureza_saldo=row.get("NATUREZA"),
        )
'''


G["tron"]["src/extract/tron/firebird_extractor.py"] = r'''"""Conexão Firebird com a Tron (opções + listagem de tabelas)."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TronConnectionOptions:
    """Credenciais do Firebird da Tron."""

    host: str
    database: str
    usuario: str
    senha: str
    porta: int = 3050
    charset: str = "UTF8"


class TronFirebirdExtractor:
    """Wrapper de conexão — extração real fica em `tron_extractor.TronExtractor`."""

    def __init__(self, opt: TronConnectionOptions) -> None:
        self._opt = opt

    @contextmanager
    def conectar(self) -> Iterator[Any]:
        from firebird.driver import connect

        dsn = f"{self._opt.host}/{self._opt.porta}:{self._opt.database}"
        conn = connect(
            dsn, user=self._opt.usuario, password=self._opt.senha,
            charset=self._opt.charset,
        )
        try:
            yield conn
        finally:
            conn.close()

    def listar_tabelas(self) -> list[str]:
        with self.conectar() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT TRIM(RDB$RELATION_NAME) FROM RDB$RELATIONS "
                "WHERE RDB$SYSTEM_FLAG = 0 ORDER BY 1"
            )
            return [str(r[0]).strip() for r in cur.fetchall()]
'''


# =====================================================================
#  SPED
# =====================================================================
G["sped"]["src/transform/mappings/sped_para_erp_map.py"] = r'''"""Dicionário De-Para SPED → ERP.

Índices referem-se à posição em `campos` (0 = primeiro após o código),
conforme Guia Prático EFD ICMS/IPI.
"""
from __future__ import annotations


class SpedParaErpMap:
    # 0150 — Participantes
    # |0150|COD_PART|NOME|COD_PAIS|CNPJ|CPF|IE|COD_MUN|SUFRAMA|END|...
    R0150: dict[int, str] = {
        0: "codigo_origem",
        1: "razao_social",
        3: "documento_cnpj",
        4: "documento_cpf",
        5: "inscricao_estadual",
        6: "municipio",
    }

    # 0500 — Plano de contas
    # |0500|DT_ALT|COD_NAT_CC|IND_CTA|NIVEL|COD_CTA|NOME_CTA|
    #   IND_CTA: S = Sintética, A = Analítica
    R0500: dict[int, str] = {
        2: "natureza",     # IND_CTA (S/A) — corrigido vs. Stage 3
        3: "grau",
        4: "codigo",
        5: "nome",
    }
'''


G["sped"]["src/transform/sped/transformers.py"] = r'''"""Transformers SPED → entidades do ERP (0150 → participante, 0500 → conta)."""
from __future__ import annotations

from src.domain.models.chunk import TransformResult
from src.domain.models.entities.conta_contabil import ContaContabil
from src.domain.models.entities.participante import ParticipanteDestino
from src.domain.models.entities.sped_registro import SpedRegistro
from src.transform.normalizers.normalizers import Normalizers
from src.transform.validators.cpf_cnpj import CpfCnpjValidator


def _campo(reg: SpedRegistro, i: int) -> str:
    """Retorna `campos[i]` ou string vazia, sem IndexError."""
    return reg.campos[i] if i < len(reg.campos) else ""


class SpedR0150ToParticipante:
    """Transforma um registro 0150 em ParticipanteDestino."""

    def transform(self, reg: SpedRegistro) -> TransformResult[ParticipanteDestino]:
        try:
            codigo = int(_campo(reg, 0) or 0)
        except ValueError:
            return TransformResult.falha(f"0150 código inválido: {_campo(reg, 0)!r}")

        cnpj = Normalizers.documento(_campo(reg, 3))
        cpf = Normalizers.documento(_campo(reg, 4))
        documento = cnpj or cpf or ""
        tipo = "JURIDICA" if cnpj else "FISICA"

        ok, motivo = CpfCnpjValidator.validar(documento, tipo)
        if not ok:
            return TransformResult.falha(motivo or "Documento inválido no 0150")

        return TransformResult.ok(ParticipanteDestino(
            codigo_origem=codigo,
            razao_social=Normalizers.texto(_campo(reg, 1)) or "(sem razão social)",
            nome_fantasia=None,
            documento=documento,
            tipo_pessoa=tipo,
            inscricao_estadual=Normalizers.documento(_campo(reg, 5)),
            municipio=Normalizers.texto(_campo(reg, 6)),
            uf=None,
            cep=None,
            email=None,
            telefone=None,
            origem_sistema="SPED",
        ))


class SpedR0500ToContaContabil:
    """Transforma um registro 0500 em ContaContabil."""

    def transform(self, reg: SpedRegistro) -> TransformResult[ContaContabil]:
        ind = _campo(reg, 2).strip().upper()
        natureza = "SINTETICA" if ind == "S" else "ANALITICA"

        codigo = _campo(reg, 4).strip()
        if not codigo:
            return TransformResult.falha("0500 sem COD_CTA")

        try:
            grau = int(_campo(reg, 3) or 1)
        except ValueError:
            grau = 1

        # Natureza de saldo: sintéticas não precisam; analíticas exigem D/C.
        # SPED 0500 não traz saldo — inferimos pelo primeiro dígito do código.
        natureza_saldo = None
        if natureza == "ANALITICA":
            primeiro = codigo.split(".")[0] if codigo else ""
            natureza_saldo = "DEVEDORA" if primeiro in ("1", "4", "5", "7") else "CREDORA"

        return TransformResult.ok(ContaContabil(
            codigo=codigo,
            nome=Normalizers.texto(_campo(reg, 5)) or codigo,
            codigo_pai=None,  # SPED não informa pai explicitamente
            natureza=natureza,
            grau=grau,
            natureza_saldo=natureza_saldo,
        ))
'''


# =====================================================================
#  SYNC
# =====================================================================
G["sync"]["src/infrastructure/sync/__init__.py"] = '"""Sincronizador Delta local→nuvem."""\n'


G["sync"]["src/infrastructure/sync/delta_client.py"] = r'''"""Cliente HTTP para enviar lotes de eventos ao endpoint de sync na nuvem."""
from __future__ import annotations

from typing import Any

import httpx

from src.infrastructure.resilience.retry_policy import RetryPolicy


class DeltaClient:
    """Envia um lote de eventos para a API de sync na nuvem.

    Contrato esperado do servidor:
        POST {base_url}/api/sync/batch
        Authorization: Bearer {api_key}
        Body: {
            "lote_id": "...",
            "empresa_id": "...",
            "eventos": [
                {"entidade": "participante", "operacao": "UPSERT", "dados": {...}},
                {"entidade": "participante", "operacao": "DELETE", "registro_id": "123"}
            ]
        }
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout_s: float = 15.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout_s
        self._retry = RetryPolicy(tentativas=3, backoff_inicial_s=1.0)

    def enviar(self, lote: dict[str, Any]) -> bool:
        """Envia o lote; retorna True em 2xx. Retry exponencial em falhas."""
        url = f"{self._base_url}/api/sync/batch"
        headers = {"Authorization": f"Bearer {self._api_key}"}

        def _tentativa() -> bool:
            with httpx.Client(timeout=self._timeout) as client:
                r = client.post(url, json=lote, headers=headers)
            if r.status_code >= 500:
                raise RuntimeError(f"cloud 5xx: {r.status_code}")
            if r.status_code >= 400:
                raise httpx.HTTPStatusError(
                    f"cloud {r.status_code}: {r.text[:200]}",
                    request=r.request, response=r,
                )
            return True

        try:
            return self._retry.executar(_tentativa)
        except Exception:
            return False
'''


G["sync"]["src/infrastructure/sync/sync_worker.py"] = r'''"""Worker que drena a outbox local e envia deltas para a nuvem."""
from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.infrastructure.sync.delta_client import DeltaClient

log = logging.getLogger(__name__)


# entidade → (tabela_origem, coluna_chave_natural)
_TABELAS: dict[str, tuple[str, str]] = {
    "participante":   ("erp.participante",    "codigo_origem"),
    "empresa":        ("erp.empresa",         "codigo_origem"),
    "conta_contabil": ("erp.conta_contabil",  "codigo"),
}

_LOTE_MAX_TENTATIVAS = 5
_BACKOFF_BASE_S = 30.0
_BACKOFF_MAX_S = 900.0  # 15 min


@dataclass(slots=True)
class _EventoOutbox:
    id: str
    empresa_id: str
    entidade: str
    operacao: str
    registro_id: str
    tentativas: int


class SyncWorker:
    """Drena `sync.sync_outbox` em lotes e envia para a nuvem.

    Uso:
        worker = SyncWorker(conninfo, base_url, api_key)
        worker.start()
        ...
        worker.stop()
    """

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
        """Processa até `batch_size` eventos pendentes. Retorna quantos foram OK."""
        with psycopg.connect(self._conninfo, row_factory=dict_row) as conn:
            with conn.transaction():
                eventos = self._pegar_lote(conn)
                if not eventos:
                    return 0

                # Agrupa por (empresa_id, entidade) — cada POST cobre uma empresa.
                por_empresa: dict[str, list[_EventoOutbox]] = {}
                for ev in eventos:
                    por_empresa.setdefault(ev.empresa_id, []).append(ev)

                total_ok = 0
                for empresa_id, evs in por_empresa.items():
                    ok, falhas = self._enviar_empresa(conn, empresa_id, evs)
                    total_ok += ok
                    self._marcar(conn, evs, falhas)
                return total_ok

    def _pegar_lote(self, conn: psycopg.Connection) -> list[_EventoOutbox]:
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
            return [
                _EventoOutbox(
                    id=str(r["id"]), empresa_id=r["empresa_id"],
                    entidade=r["entidade"], operacao=r["operacao"],
                    registro_id=r["registro_id"], tentativas=r["tentativas"],
                )
                for r in cur.fetchall()
            ]

    def _enviar_empresa(
        self, conn: psycopg.Connection, empresa_id: str,
        eventos: list[_EventoOutbox],
    ) -> tuple[int, dict[str, str]]:
        """Monta o payload com os dados atuais e POSTa. Retorna (ok, erros por id)."""
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
        self, conn: psycopg.Connection, ev: _EventoOutbox,
    ) -> dict[str, Any] | None:
        tabela, coluna_chave = _TABELAS.get(ev.entidade, (None, None))
        if tabela is None:
            return None
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM {tabela} WHERE empresa_id = %s AND {coluna_chave} = %s",
                (ev.empresa_id, ev.registro_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def _marcar(
        self, conn: psycopg.Connection, evs: list[_EventoOutbox],
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


# =====================================================================
#  LOAD — outbox writer reescrito
# =====================================================================
G["load"]["src/load/sync_outbox_writer.py"] = r'''"""Transactional Outbox para o Sincronizador Delta."""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.domain.enums.enums import OperacaoSync

if TYPE_CHECKING:
    from psycopg import Connection


_INSERT_SQL = """
    INSERT INTO sync.sync_outbox (empresa_id, entidade, operacao, registro_id)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (empresa_id, entidade, registro_id)
        WHERE sincronizado_em IS NULL
    DO UPDATE SET operacao = EXCLUDED.operacao,
                  agendado_para = now(),
                  tentativas = 0
"""


class SyncOutboxWriter:
    """Enfileira eventos na MESMA transação do Load.

    Notes:
        - Um evento por registro (não por lote).
        - Coalesce: se já há evento pendente, atualiza a operação — evita
          duplicar UPSERT+DELETE do mesmo registro em lotes consecutivos.
    """

    def enfileirar_batch(
        self,
        conn: Connection,
        empresa_id: str,
        entidade: str,
        registro_ids: list[str],
        operacao: OperacaoSync,
    ) -> int:
        if not registro_ids:
            return 0
        with conn.cursor() as cur:
            cur.executemany(
                _INSERT_SQL,
                [(empresa_id, entidade, operacao.value, rid) for rid in registro_ids],
            )
        return len(registro_ids)
'''


# =====================================================================
#  ORCHESTRATOR
# =====================================================================
G["orchestrator"]["src/infrastructure/orchestrator.py"] = r'''"""Orquestrador: pipeline genérico (Empresa + Plano + Participante + SPED)."""
from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
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
from src.transform.sped.transformers import (
    SpedR0150ToParticipante,
    SpedR0500ToContaContabil,
)


@dataclass(slots=True)
class _Etapa:
    nome: str
    entidade: str                 # participante | empresa | conta_contabil | NONE
    extractor: Any
    transformer: Any | None
    loader: Callable[[psycopg.Connection, str, list[Any]], int]
    fallback: Callable[[psycopg.Connection, str, list[Any]], int]
    sync: bool = True             # se False, não enfileira na outbox
    id_fn: Callable[[Any], str] = field(default=lambda _: "")


def _id_codigo_origem(item: Any) -> str:
    return str(getattr(item, "codigo_origem"))


def _id_codigo(item: Any) -> str:
    return str(getattr(item, "codigo"))


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
                loader=lambda conn, eid, itens: self._bulk.inserir_sped(conn, eid, itens),
                fallback=lambda conn, eid, itens: self._fallback.inserir_sped(conn, eid, itens),
                sync=False,  # SPED de auditoria não sobe para a nuvem
            )
            for c in caminhos
        ]
        return self._executar("SPED", empresa_id, etapas, progresso)

    # -- Arquivos (SPED estruturado: 0150 → participante, 0500 → conta)
    def executar_migracao_sped_estruturada(
        self,
        caminhos: list[str],
        empresa_id: str,
        progresso: Callable[[MigrationProgress], None],
    ) -> MigrationResult:
        """Extrai registros 0150 e 0500 dos .txt e grava em erp.*."""
        etapas: list[_Etapa] = []
        for c in caminhos:
            etapas.append(_Etapa(
                nome=f"sped-0150:{Path(c).name}", entidade="participante",
                extractor=SpedTxtExtractor(Path(c)),
                transformer=SpedR0150ToParticipante(),
                loader=lambda conn, eid, itens: self._bulk.inserir_participantes(conn, None, eid, itens),
                fallback=lambda conn, eid, itens: self._fallback.inserir_participantes(conn, None, eid, itens),
                id_fn=_id_codigo_origem,
            ))
            etapas.append(_Etapa(
                nome=f"sped-0500:{Path(c).name}", entidade="conta_contabil",
                extractor=SpedTxtExtractor(Path(c)),
                transformer=SpedR0500ToContaContabil(),
                loader=lambda conn, eid, itens: self._bulk.inserir_contas(conn, eid, itens),
                fallback=lambda conn, eid, itens: self._fallback.inserir_contas(conn, eid, itens),
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
        if callable(getattr(extractor, "count_estimado", None)):
            try:
                return extractor.count_estimado()
            except Exception:
                return None
        return None

    @staticmethod
    def _iterar(extractor: Any) -> Iterable[Any]:
        return extractor.extract()

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
                loader=lambda c, eid, itens: self._bulk.inserir_empresas(c, eid, itens),
                fallback=lambda c, eid, itens: self._fallback.inserir_empresas(c, eid, itens),
                id_fn=_id_codigo_origem,
            ),
            "plano_contas": _Etapa(
                nome="plano_contas", entidade="conta_contabil",
                extractor=FortesPlanoContasExtractor(factory, opt.tamanho_chunk),
                transformer=None,
                loader=lambda c, eid, itens: self._bulk.inserir_contas(c, eid, itens),
                fallback=lambda c, eid, itens: self._fallback.inserir_contas(c, eid, itens),
                id_fn=_id_codigo,
            ),
            "participante": _Etapa(
                nome="participante", entidade="participante",
                extractor=FortesParticipanteExtractor(factory, opt.tamanho_chunk),
                transformer=self._transformer,
                loader=lambda c, eid, itens: self._bulk.inserir_participantes(c, None, eid, itens),
                fallback=lambda c, eid, itens: self._fallback.inserir_participantes(c, None, eid, itens),
                id_fn=_id_codigo_origem,
            ),
        }
        faltando = [n for n in etapas if n not in mapa]
        if faltando:
            raise ValueError(f"Etapas desconhecidas: {faltando}")
        return [mapa[n] for n in etapas]
'''


# =====================================================================
#  WEB
# =====================================================================
G["web"]["src/web/auth.py"] = r'''"""Autenticação HTTP Basic para o painel Admin."""
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

    ok_user = secrets.compare_digest(creds.username, usuario_esperado)
    ok_senha = secrets.compare_digest(creds.password, senha_esperada)
    if not (ok_user and ok_senha):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
            headers={"WWW-Authenticate": "Basic"},
        )
    return creds.username
'''


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
'''


G["web"]["src/web/app.py"] = r'''"""Painel Admin — Utilitários de Migração (FastAPI + Auth Basic)."""
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
    """Extrai 0150 → erp.participante e 0500 → erp.conta_contabil."""
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
    return JobResponse(job_id=job_id, status="EM_ANDAMENTO",
                       descricao=f"SPED estruturado ({len(req.caminhos)} arquivo(s))")


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
@app.get("/api/migracao/sync/status", response_model=SyncStatusResponse)
def sync_status(_user: str = Depends(verificar_admin)) -> SyncStatusResponse:
    with psycopg.connect(CONNINFO, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE sincronizado_em IS NULL AND agendado_para <= now() AND tentativas < 5) AS pendentes,
                COUNT(*) FILTER (WHERE sincronizado_em IS NULL AND agendado_para > now()) AS agendados,
                COUNT(*) FILTER (WHERE sincronizado_em IS NULL AND tentativas >= 5) AS com_erro,
                COUNT(*) FILTER (WHERE sincronizado_em > now() - interval '24 hours') AS sincronizados_24h
            FROM sync.sync_outbox
        """)
        row = cur.fetchone()
        dlq = conn.execute("SELECT COUNT(*) FROM sync.sync_dlq").fetchone()
    return SyncStatusResponse(
        pendentes=row[0], agendados=row[1], com_erro=row[2],
        sincronizados_24h=row[3], dlq_total=dlq[0] if dlq else 0,
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
    <h2>📊 Sincronizador Delta (nuvem)</h2>
    <p id="sync-resumo">carregando…</p>
  </section>

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
        <label><input type="checkbox" name="etapas" value="plano_contas" checked> Plano</label>
        <label><input type="checkbox" name="etapas" value="participante" checked> Participantes</label>
      </fieldset>
      <div class="actions">
        <button type="button" id="fortes-test">Testar conexão</button>
        <button type="submit">Iniciar migração</button>
      </div>
    </form>
  </section>

  <section class="card">
    <h2>2) SPED .txt / NF-e .xml</h2>
    <div id="dropzone" class="dropzone">
      Arraste arquivos .txt (SPED) ou .xml (NF-e) aqui, ou
      <input type="file" id="arquivo-input" multiple accept=".txt,.xml">
    </div>
    <label>Empresa ID <input id="empresa-id-arq" required></label>
    <ul id="lista-arquivos"></ul>
    <div class="actions">
      <button id="arq-iniciar" disabled>Auditar SPED (grava em sped_registro)</button>
      <button id="arq-estruturar" disabled>Importar SPED estruturado (0150+0500 → ERP)</button>
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


G["web"]["src/web/static/app.js"] = r'''/* Painel Admin — polling, upload, sync e SPED estruturado. */
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
    } catch { $("#health").textContent = "🔴 API offline"; }
  }

  async function syncStatus() {
    try {
      const r = await fetch("/api/migracao/sync/status");
      if (!r.ok) { $("#sync-resumo").textContent = "auth necessária"; return; }
      const d = await r.json();
      $("#sync-resumo").textContent =
        `⏳ Pendentes: ${fmt(d.pendentes)} · ` +
        `🕐 Agendados: ${fmt(d.agendados)} · ` +
        `⚠️ Com erro: ${fmt(d.com_erro)} · ` +
        `✅ Últimas 24h: ${fmt(d.sincronizados_24h)} · ` +
        `💀 DLQ: ${fmt(d.dlq_total)}`;
    } catch { $("#sync-resumo").textContent = "erro"; }
  }

  async function testarFortes() {
    const form = $("#fortes-form");
    const data = Object.fromEntries(new FormData(form).entries());
    data.porta = parseInt(data.porta, 10);
    delete data.etapas;
    const r = await fetch("/api/migracao/fortes/testar", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!r.ok) { alert("Auth ou erro: " + (await r.text())); return; }
    const d = await r.json();
    alert(d.ok ? "✅ Conexão OK" : "❌ Falha (ver migracao_erros.log)");
  }

  async function iniciarFortes(e) {
    e.preventDefault();
    const form = $("#fortes-form");
    const data = Object.fromEntries(new FormData(form).entries());
    data.porta = parseInt(data.porta, 10);
    data.etapas = [...form.querySelectorAll("input[name=etapas]:checked")]
      .map((i) => i.value);
    if (!data.etapas.length) { alert("Selecione ao menos uma etapa"); return; }
    const r = await fetch("/api/migracao/fortes/iniciar", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!r.ok) { alert("Erro: " + (await r.text())); return; }
    acompanhar((await r.json()).job_id);
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
    $("#arq-estruturar").disabled = uploads.length === 0;
  }

  async function enviarArquivos(files) {
    const empresaId = $("#empresa-id-arq").value.trim();
    if (!empresaId) { alert("Preencha Empresa ID antes"); return; }
    const fd = new FormData();
    for (const f of files) fd.append("arquivos", f);
    const r = await fetch(
      `/api/migracao/arquivos/upload?empresa_id=${encodeURIComponent(empresaId)}`,
      { method: "POST", body: fd },
    );
    if (!r.ok) { alert("Erro upload: " + (await r.text())); return; }
    const d = await r.json();
    d.arquivos.forEach((p, i) => uploads.push({ caminho: p, nome: files[i].name }));
    renderUploads();
  }

  async function iniciarArquivos() {
    const empresaId = $("#empresa-id-arq").value.trim();
    const caminhos = uploads.map((u) => u.caminho);
    const r = await fetch(
      `/api/migracao/arquivos/iniciar?empresa_id=${encodeURIComponent(empresaId)}`,
      { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(caminhos) },
    );
    if (!r.ok) { alert("Erro: " + (await r.text())); return; }
    acompanhar((await r.json()).job_id);
  }

  async function iniciarSpedEstruturado() {
    const empresaId = $("#empresa-id-arq").value.trim();
    const caminhos = uploads.map((u) => u.caminho);
    const r = await fetch("/api/migracao/arquivos/estruturado", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ empresa_id: empresaId, caminhos }),
    });
    if (!r.ok) { alert("Erro: " + (await r.text())); return; }
    acompanhar((await r.json()).job_id);
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
        $("#etapa").textContent = d.status === "CONCLUIDO"
          ? "✅ Concluído" : "❌ " + (d.erro || "falhou");
      }
    }, 1000);
  }

  // bindings
  $("#fortes-test").addEventListener("click", testarFortes);
  $("#fortes-form").addEventListener("submit", iniciarFortes);
  $("#arq-iniciar").addEventListener("click", iniciarArquivos);
  $("#arq-estruturar").addEventListener("click", iniciarSpedEstruturado);
  $("#arquivo-input").addEventListener("change", (e) => enviarArquivos(e.target.files));
  $("#dropzone").addEventListener("dragover", (e) => e.preventDefault());
  $("#dropzone").addEventListener("drop", (e) => {
    e.preventDefault();
    if (e.dataTransfer?.files?.length) enviarArquivos(e.dataTransfer.files);
  });

  health(); syncStatus();
  setInterval(health, 30_000);
  setInterval(syncStatus, 15_000);
})();
'''


# =====================================================================
#  SCRIPTS
# =====================================================================
G["scripts"]["scripts/run_sync_worker.py"] = r'''#!/usr/bin/env python3
"""Sobe o SyncWorker (processo separado do painel)."""
from __future__ import annotations

import os
import signal
import sys
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


G["scripts"]["scripts/demo_sped_transform.py"] = r'''#!/usr/bin/env python3
"""Demo: SPED estruturado (0150 → participante, 0500 → conta)."""
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
    p.add_argument("arquivos", nargs="+")
    p.add_argument("--empresa-id", required=True)
    p.add_argument("--conninfo", default=os.environ.get(
        "ERP_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/erp_contabil"))
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


# =====================================================================
#  TESTS
# =====================================================================
G["tests"]["tests/test_sped_transformers.py"] = r'''"""Testes dos transformers SPED → ERP."""
from __future__ import annotations

from src.domain.models.entities.sped_registro import SpedRegistro
from src.transform.sped.transformers import (
    SpedR0150ToParticipante,
    SpedR0500ToContaContabil,
)


def _reg(codigo: str, *campos: str) -> SpedRegistro:
    return SpedRegistro(codigo=codigo, campos=tuple(campos), linha_bruta="|x|")


def test_0150_pj_valido() -> None:
    reg = _reg("0150", "P001", "Fornecedor XYZ", "1058",
               "11222333000181", "", "123456789", "3550308")
    r = SpedR0150ToParticipante().transform(reg)
    assert r.sucesso is True
    assert r.valor is not None
    assert r.valor.razao_social == "Fornecedor XYZ"
    assert r.valor.documento == "11222333000181"
    assert r.valor.tipo_pessoa == "JURIDICA"
    assert r.valor.origem_sistema == "SPED"


def test_0150_pf_valido() -> None:
    reg = _reg("0150", "P002", "João da Silva", "1058",
               "", "52998224725", "", "")
    r = SpedR0150ToParticipante().transform(reg)
    assert r.sucesso is True
    assert r.valor is not None
    assert r.valor.documento == "52998224725"
    assert r.valor.tipo_pessoa == "FISICA"


def test_0150_documento_invalido() -> None:
    reg = _reg("0150", "P003", "Empresa Ruim", "1058",
               "00000000000000", "", "", "")
    r = SpedR0150ToParticipante().transform(reg)
    assert r.sucesso is False
    assert r.motivo is not None and "CNPJ" in r.motivo


def test_0500_sintetica() -> None:
    # DT_ALT, COD_NAT_CC, IND_CTA, NIVEL, COD_CTA, NOME_CTA
    reg = _reg("0500", "01012024", "01", "S", "1", "1", "ATIVO")
    r = SpedR0500ToContaContabil().transform(reg)
    assert r.sucesso is True
    assert r.valor is not None
    assert r.valor.natureza == "SINTETICA"
    assert r.valor.codigo == "1"
    assert r.valor.grau == 1


def test_0500_analitica() -> None:
    reg = _reg("0500", "01012024", "01", "A", "4", "1.1.01.001", "CAIXA")
    r = SpedR0500ToContaContabil().transform(reg)
    assert r.sucesso is True
    assert r.valor is not None
    assert r.valor.natureza == "ANALITICA"
    assert r.valor.natureza_saldo == "DEVEDORA"  # código "1.x" = ativo


def test_0500_sem_codigo_falha() -> None:
    reg = _reg("0500", "01012024", "01", "A", "4", "", "SEM CÓDIGO")
    r = SpedR0500ToContaContabil().transform(reg)
    assert r.sucesso is False
    assert r.motivo is not None and "COD_CTA" in r.motivo
'''


G["tests"]["tests/test_sync_worker.py"] = r'''"""Testes do SyncWorker (usa mock do DeltaClient, sem tocar nuvem)."""
from __future__ import annotations

import os
import uuid
from typing import Any

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


class _MockClient:
    def __init__(self, resposta: bool = True) -> None:
        self._resposta = resposta
        self.payloads: list[dict[str, Any]] = []

    def enviar(self, lote: dict[str, Any]) -> bool:
        self.payloads.append(lote)
        return self._resposta


def _inserir_evento(conn: psycopg.Connection, empresa: str, entidade: str,
                    registro_id: str, operacao: str = "UPSERT") -> str:
    rid = str(uuid.uuid4())
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO sync.sync_outbox "
            "(id, empresa_id, entidade, operacao, registro_id) "
            "VALUES (%s, %s, %s, %s, %s)",
            (rid, empresa, entidade, operacao, registro_id),
        )
    return rid


def test_worker_processa_upsert(db_ok: bool) -> None:
    from src.infrastructure.sync.sync_worker import SyncWorker

    if not db_ok:
        return
    empresa = f"test-{uuid.uuid4().hex[:8]}"
    with psycopg.connect(_conninfo()) as conn:
        # cria um participante real
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO erp.participante "
                "(empresa_id, codigo_origem, origem_sistema, razao_social, "
                " documento, tipo_pessoa) "
                "VALUES (%s, 1, 'TEST', 'Foo', '11222333000181', 'JURIDICA')",
                (empresa,),
            )
        ev_id = _inserir_evento(conn, empresa, "participante", "1")
        conn.commit()

        mock = _MockClient(resposta=True)
        worker = SyncWorker(_conninfo(), "http://mock", "key", client=mock)
        n = worker.processar_um_lote()

        assert n >= 1
        assert any(
            any(e.get("registro_id") == "1" and e.get("operacao") == "UPSERT"
                for e in p["eventos"])
            for p in mock.payloads
        )

        with conn.cursor() as cur:
            cur.execute(
                "SELECT sincronizado_em FROM sync.sync_outbox WHERE id = %s",
                (ev_id,),
            )
            row = cur.fetchone()
            assert row is not None and row[0] is not None

        conn.execute("DELETE FROM erp.participante WHERE empresa_id = %s", (empresa,))
        conn.commit()


def test_worker_falha_incrementa_tentativas(db_ok: bool) -> None:
    from src.infrastructure.sync.sync_worker import SyncWorker

    if not db_ok:
        return
    empresa = f"test-{uuid.uuid4().hex[:8]}"
    with psycopg.connect(_conninfo()) as conn:
        ev_id = _inserir_evento(conn, empresa, "participante", "999")
        conn.commit()

        mock = _MockClient(resposta=False)
        worker = SyncWorker(_conninfo(), "http://mock", "key", client=mock)
        worker.processar_um_lote()

        with conn.cursor() as cur:
            cur.execute(
                "SELECT tentativas, sincronizado_em FROM sync.sync_outbox WHERE id = %s",
                (ev_id,),
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] >= 1
            assert row[1] is None

        conn.execute("DELETE FROM sync.sync_outbox WHERE id = %s", (ev_id,))
        conn.commit()
'''


G["tests"]["tests/test_auth.py"] = r'''"""Testes de autenticação HTTP Basic do painel."""
from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient


def _basic(user: str, senha: str) -> dict[str, str]:
    token = base64.b64encode(f"{user}:{senha}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "senha-forte-123")
    # Recarrega o módulo após alterar env (o auth lê env em runtime, mas
    # queremos um TestClient limpo)
    from src.web.app import app
    return TestClient(app, raise_server_exceptions=False)


def test_health_publico(client: TestClient) -> None:
    r = client.get("/api/migracao/health")
    assert r.status_code == 200


def test_rota_protegida_sem_credenciais(client: TestClient) -> None:
    r = client.post("/api/migracao/fortes/testar", json={
        "host": "x", "database": "y", "usuario": "z", "senha": "w",
    })
    assert r.status_code == 401
    assert "WWW-Authenticate" in r.headers


def test_rota_protegida_senha_errada(client: TestClient) -> None:
    r = client.post(
        "/api/migracao/fortes/testar",
        json={"host": "x", "database": "y", "usuario": "z", "senha": "w"},
        headers=_basic("admin", "senha-errada"),
    )
    assert r.status_code == 401


def test_admin_sem_env_falha_fechado(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    r = client.post(
        "/api/migracao/fortes/testar",
        json={"host": "x", "database": "y", "usuario": "z", "senha": "w"},
        headers=_basic("admin", "qualquer"),
    )
    assert r.status_code == 500
'''


# =====================================================================
#  CONFIG
# =====================================================================
G["config"]["requirements-stage4.txt"] = r'''# Stage 4 — sync delta (o restante já vem do requirements-web.txt)
httpx>=0.27.0
'''


G["config"]["pyproject.toml"] = r'''[project]
name = "erp-contabil-migracao"
version = "0.4.0"
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
"src/web/app.py" = ["B008"]
"scripts/*.py" = ["T201"]
"tests/test_auth.py" = ["S105", "S106"]   # senhas literais em tests

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
        pfx = {"ddl": "🗄️ ", "tron": "🔥", "sped": "📄", "sync": "🔄",
               "load": "⬇️ ", "orchestrator": "🏗️ ", "web": "🌐",
               "scripts": "📜", "tests": "🧪", "config": "⚙️ "}[grupo]
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
    parser.add_argument(
        "--only",
        choices=["ddl", "tron", "sped", "sync", "load",
                 "orchestrator", "web", "scripts", "tests", "config", "all"],
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
    print("  1. pip install -r requirements-stage4.txt")
    print("  2. psql -d erp_contabil -f ddl/schema_stage4.sql")
    print("  3. Configurar env vars:")
    print("     export ADMIN_USER=admin")
    print("     export ADMIN_PASSWORD='senha-forte-aqui'")
    print("     export CLOUD_SYNC_URL='https://erp.example.com'")
    print("     export CLOUD_SYNC_API_KEY='chave-secreta'")
    print("  4. Painel protegido:  ./scripts/run_admin.sh")
    print("  5. Worker delta:      python scripts/run_sync_worker.py")
    print("  6. Verificação:       pytest -v && mypy src/ && ruff check src/")
    return 0


if __name__ == "__main__":
    sys.exit(main())