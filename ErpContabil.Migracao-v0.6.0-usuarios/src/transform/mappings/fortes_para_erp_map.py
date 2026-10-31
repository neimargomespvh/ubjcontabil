"""Dicionário De-Para Fortes → ERP."""
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
