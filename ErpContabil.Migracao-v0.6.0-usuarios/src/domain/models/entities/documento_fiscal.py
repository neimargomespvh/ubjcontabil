"""Entidades de documento fiscal e itens (SPED C100 / C170)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class DocumentoFiscal:
    """Cabeçalho de documento fiscal (registro C100 do SPED).

    Attributes:
        chave_nfe: chave de acesso de 44 dígitos (pode ser vazia em modelos não-eletrônicos).
        numero: número do documento (NUM_DOC).
        serie: série (SER).
        modelo: código do modelo (COD_MOD, ex.: 55 = NF-e).
        data_emissao: DT_DOC no formato AAAAMMDD ou vazio.
        data_entrada_saida: DT_E_S.
        ind_oper: "0" entrada / "1" saída.
        ind_emit: "0" emissão própria / "1" terceiros.
        cod_part: código do participante (referencia 0150).
        cod_sit: situação do documento (00=regular, etc.).
        valor_documento: VL_DOC.
        valor_mercadoria: VL_MERC.
        valor_desconto: VL_DESC.
        valor_icms: VL_ICMS.
        valor_ipi: VL_IPI.
        valor_pis: VL_PIS.
        valor_cofins: VL_COFINS.
        origem_sistema: sempre "SPED" neste fluxo.
        codigo_origem: identificador estável para outbox/upsert
            (preferencialmente a chave NF-e; senão modelo+serie+numero).
    """

    chave_nfe: str
    numero: str
    serie: str
    modelo: str
    data_emissao: str
    data_entrada_saida: str
    ind_oper: str
    ind_emit: str
    cod_part: str
    cod_sit: str
    valor_documento: Decimal
    valor_mercadoria: Decimal
    valor_desconto: Decimal
    valor_icms: Decimal
    valor_ipi: Decimal
    valor_pis: Decimal
    valor_cofins: Decimal
    origem_sistema: str
    codigo_origem: str


@dataclass(frozen=True, slots=True)
class ItemDocumentoFiscal:
    """Item de documento fiscal (registro C170 do SPED).

    Attributes:
        num_item: número sequencial do item no documento.
        cod_item: código do item (referencia 0200 quando existir).
        descricao: DESCR_COMPL.
        quantidade: QTD.
        unidade: UNID.
        valor_item: VL_ITEM.
        valor_desconto: VL_DESC.
        cfop: CFOP.
        cst_icms: CST_ICMS (ou CSOSN em alguns casos).
        valor_bc_icms: VL_BC_ICMS.
        aliquota_icms: ALIQ_ICMS.
        valor_icms: VL_ICMS.
        documento_codigo_origem: chave do documento pai (para vínculo).
        origem_sistema: "SPED".
        codigo_origem: identificador estável do item
            (documento_codigo_origem + "#" + num_item).
    """

    num_item: int
    cod_item: str
    descricao: str | None
    quantidade: Decimal
    unidade: str | None
    valor_item: Decimal
    valor_desconto: Decimal
    cfop: str
    cst_icms: str
    valor_bc_icms: Decimal
    aliquota_icms: Decimal
    valor_icms: Decimal
    documento_codigo_origem: str
    origem_sistema: str
    codigo_origem: str
