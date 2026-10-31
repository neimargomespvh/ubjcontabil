"""Validação de CPF e CNPJ pelo dígito verificador."""
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
