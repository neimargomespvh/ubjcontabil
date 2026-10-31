"""Normalizações de texto, documento, UF, e-mail e telefone."""
from __future__ import annotations

UFS_IBGE: frozenset[str] = frozenset({
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
})


class Normalizers:
    """Funções puras de normalização de campos.

    Notes:
        - Todas as funções retornam `None` quando o valor de entrada é vazio,
          para facilitar o INSERT como NULL no PostgreSQL.
        - Nenhuma função lança exceção: entradas inválidas viram `None`.
    """

    @staticmethod
    def texto(v: str | None) -> str | None:
        """Trim, colapsa espaços internos, retorna None se vazio."""
        if v is None:
            return None
        limpo = " ".join(v.strip().split())
        return limpo or None

    @staticmethod
    def documento(v: str | None) -> str | None:
        """Mantém só dígitos."""
        if v is None:
            return None
        d = "".join(c for c in v if c.isdigit())
        return d or None

    @staticmethod
    def uf(v: str | None) -> str | None:
        """Uppercase e valida contra a lista de UFs do IBGE."""
        if v is None:
            return None
        uf = v.strip().upper()
        return uf if uf in UFS_IBGE else None

    @staticmethod
    def email(v: str | None) -> str | None:
        """Lowercase e trim. Retorna None se não contiver '@'."""
        if v is None:
            return None
        e = v.strip().lower()
        return e if "@" in e else None

    @staticmethod
    def telefone(v: str | None) -> str | None:
        """Mantém só dígitos. Retorna None se tiver menos de 10 dígitos."""
        if v is None:
            return None
        d = "".join(c for c in v if c.isdigit())
        return d if len(d) >= 10 else None
