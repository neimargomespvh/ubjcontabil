"""Parser de linhas do SPED."""
from __future__ import annotations

from src.domain.models.entities.sped_registro import SpedRegistro


class SpedLineParser:
    """Converte uma linha bruta do SPED em SpedRegistro.

    Formato: |REG|campo1|campo2|...|
    """

    @staticmethod
    def parse(linha: str) -> SpedRegistro | None:
        """Retorna None se a linha for inválida (vazia, sem pipes, curta)."""
        if not linha or not linha.startswith("|"):
            return None
        limpa = linha.rstrip("\r\n")
        partes = limpa.split("|")
        if len(partes) < 3:
            return None
        codigo = partes[1]
        if not codigo:
            return None
        # partes[0] é vazio, partes[1] é o código, partes[-1] é vazio
        campos = tuple(partes[2:-1])
        return SpedRegistro(codigo=codigo, campos=campos, linha_bruta=limpa)
