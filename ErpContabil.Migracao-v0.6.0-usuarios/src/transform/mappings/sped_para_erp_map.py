"""Dicionário De-Para SPED → ERP.

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
    R0500: dict[int, str] = {
        2: "natureza",  # IND_CTA (S/A)
        3: "grau",
        4: "codigo",
        5: "nome",
    }

    # C100 — Documento fiscal (cabeçalho)
    # |C100|IND_OPER|IND_EMIT|COD_PART|COD_MOD|COD_SIT|SER|NUM_DOC|CHV_NFE|
    #       DT_DOC|DT_E_S|VL_DOC|IND_PGTO|VL_DESC|VL_ABAT_NT|VL_MERC|...
    RC100: dict[int, str] = {
        0: "ind_oper",
        1: "ind_emit",
        2: "cod_part",
        3: "modelo",
        4: "cod_sit",
        5: "serie",
        6: "numero",
        7: "chave_nfe",
        8: "data_emissao",
        9: "data_entrada_saida",
        10: "valor_documento",
        12: "valor_desconto",
        14: "valor_mercadoria",
        20: "valor_icms",
        24: "valor_ipi",
        25: "valor_pis",
        26: "valor_cofins",
    }

    # C170 — Itens do documento
    # |C170|NUM_ITEM|COD_ITEM|DESCR_COMPL|QTD|UNID|VL_ITEM|VL_DESC|IND_MOV|
    #       CST_ICMS|CFOP|COD_NAT|VL_BC_ICMS|ALIQ_ICMS|VL_ICMS|...
    RC170: dict[int, str] = {
        0: "num_item",
        1: "cod_item",
        2: "descricao",
        3: "quantidade",
        4: "unidade",
        5: "valor_item",
        6: "valor_desconto",
        8: "cst_icms",
        9: "cfop",
        11: "valor_bc_icms",
        12: "aliquota_icms",
        13: "valor_icms",
    }
