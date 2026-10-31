"""Entidades do plano de contas contábil."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ContaContabil:
    """Uma conta do plano de contas — sintética ou analítica.

    Attributes:
        codigo: código contábil (ex.: "1.1.01.001").
        nome: descrição da conta.
        codigo_pai: código do pai na hierarquia (None para raiz).
        natureza: "SINTETICA" ou "ANALITICA".
        grau: profundidade na árvore (raiz = 1).
        natureza_saldo: "DEVEDORA" ou "CREDORA" — obrigatório se analítica.
    """

    codigo: str
    nome: str
    codigo_pai: str | None
    natureza: str
    grau: int
    natureza_saldo: str | None
