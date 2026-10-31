"""Entidade empresa (cadastro de CNPJ do escritório/cliente)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EmpresaOrigem:
    """Registro bruto de empresa extraído da base de origem."""

    codigo_origem: int
    razao_social: str | None
    cnpj: str | None
    uf: str | None
    regime_tributario: str | None
