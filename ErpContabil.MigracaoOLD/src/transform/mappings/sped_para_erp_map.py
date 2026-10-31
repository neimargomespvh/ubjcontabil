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
    #   IND_CTA: S = Sintética, A = Analítica
    R0500: dict[int, str] = {
        2: "natureza",     # IND_CTA (S/A) — corrigido vs. Stage 3
        3: "grau",
        4: "codigo",
        5: "nome",
    }
