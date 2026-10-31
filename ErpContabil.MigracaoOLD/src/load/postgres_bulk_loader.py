"""Bulk Insert no PostgreSQL via COPY ... FROM STDIN (FORMAT BINARY)."""
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
