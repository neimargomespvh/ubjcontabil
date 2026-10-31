"""Registro genérico de um arquivo SPED."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SpedRegistro:
    """Linha do SPED já fatiada em (código do registro, campos).

    Attributes:
        codigo: código do registro SPED (ex.: "0150", "C100").
        campos: campos do registro, sem o pipe inicial/final.
        linha_bruta: linha original do arquivo (para logs de erro).
        arquivo: nome do arquivo de onde veio a linha.
        numero_linha: número da linha dentro do arquivo (1-based).
    """

    codigo: str
    campos: tuple[str, ...]
    linha_bruta: str
    arquivo: str = ""
    numero_linha: int = 0
