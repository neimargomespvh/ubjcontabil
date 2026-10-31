"""Entidades de participante (cliente/fornecedor)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParticipanteOrigem:
    """Registro bruto extraído da base de origem (Fortes/Tron)."""

    codigo_origem: int
    razao_social: str | None
    nome_fantasia: str | None
    documento: str | None
    inscricao_estadual: str | None
    inscricao_municipal: str | None
    endereco: str | None
    cidade: str | None
    uf: str | None
    cep: str | None
    email: str | None
    telefone: str | None
    tipo_pessoa: str | None


@dataclass(frozen=True, slots=True)
class ParticipanteDestino:
    """Registro já validado e normalizado, pronto para o INSERT."""

    codigo_origem: int
    razao_social: str
    nome_fantasia: str | None
    documento: str
    tipo_pessoa: str                # "FISICA" | "JURIDICA"
    inscricao_estadual: str | None
    municipio: str | None
    uf: str | None
    cep: str | None
    email: str | None
    telefone: str | None
    origem_sistema: str             # "FORTES" | "TRON" | "SPED"
