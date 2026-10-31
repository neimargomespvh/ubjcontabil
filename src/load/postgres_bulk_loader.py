"""Bulk Insert no PostgreSQL via COPY ... FROM STDIN (FORMAT BINARY)."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from psycopg import sql

from src.domain.models.entities.conta_contabil import ContaContabil
from src.domain.models.entities.documento_fiscal import (
    DocumentoFiscal,
    ItemDocumentoFiscal,
)
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
_TIPOS_PARTICIPANTE = [
    "text", "int8", "text", "text", "text", "text", "text",
    "text", "text", "text", "text", "text", "text",
]

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

_COPY_DOCUMENTO = _copy_sql("documento_fiscal", [
    "empresa_id", "codigo_origem", "origem_sistema", "chave_nfe",
    "numero", "serie", "modelo", "data_emissao", "data_entrada_saida",
    "ind_oper", "ind_emit", "cod_part", "cod_sit",
    "valor_documento", "valor_mercadoria", "valor_desconto",
    "valor_icms", "valor_ipi", "valor_pis", "valor_cofins",
])
_TIPOS_DOCUMENTO = [
    "text", "text", "text", "text",
    "text", "text", "text", "text", "text",
    "text", "text", "text", "text",
    "numeric", "numeric", "numeric",
    "numeric", "numeric", "numeric", "numeric",
]

_COPY_ITEM = _copy_sql("documento_item", [
    "empresa_id", "codigo_origem", "origem_sistema", "documento_codigo_origem",
    "num_item", "cod_item", "descricao", "quantidade", "unidade",
    "valor_item", "valor_desconto", "cfop", "cst_icms",
    "valor_bc_icms", "aliquota_icms", "valor_icms",
])
_TIPOS_ITEM = [
    "text", "text", "text", "text",
    "int4", "text", "text", "numeric", "text",
    "numeric", "numeric", "text", "text",
    "numeric", "numeric", "numeric",
]


class PostgresBinaryBulkLoader:
    """Insere grandes volumes via COPY BINARY (3–10× mais rápido que INSERT)."""

    def __init__(self, connection_string: str) -> None:
        self._connection_string = connection_string

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

    def inserir_documentos(
        self,
        conn: Connection,
        empresa_id: str,
        itens: list[DocumentoFiscal],
    ) -> int:
        with conn.cursor() as cur, cur.copy(_COPY_DOCUMENTO) as copy:
            copy.set_types(_TIPOS_DOCUMENTO)
            for d in itens:
                copy.write_row((
                    empresa_id, d.codigo_origem, d.origem_sistema,
                    d.chave_nfe or None,
                    d.numero, d.serie or None, d.modelo,
                    d.data_emissao or None, d.data_entrada_saida or None,
                    d.ind_oper, d.ind_emit, d.cod_part or None, d.cod_sit,
                    d.valor_documento, d.valor_mercadoria, d.valor_desconto,
                    d.valor_icms, d.valor_ipi, d.valor_pis, d.valor_cofins,
                ))
        return len(itens)

    def inserir_itens(
        self,
        conn: Connection,
        empresa_id: str,
        itens: list[ItemDocumentoFiscal],
    ) -> int:
        with conn.cursor() as cur, cur.copy(_COPY_ITEM) as copy:
            copy.set_types(_TIPOS_ITEM)
            for i in itens:
                copy.write_row((
                    empresa_id, i.codigo_origem, i.origem_sistema,
                    i.documento_codigo_origem, i.num_item, i.cod_item,
                    i.descricao, i.quantidade, i.unidade,
                    i.valor_item, i.valor_desconto,
                    i.cfop or None, i.cst_icms or None,
                    i.valor_bc_icms, i.aliquota_icms, i.valor_icms,
                ))
        return len(itens)
