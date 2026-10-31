"""Fallback linha-a-linha com SAVEPOINT para o caso de COPY falhar."""
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
