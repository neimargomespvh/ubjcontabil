"""Entidades de domínio do migrador."""
from src.domain.models.entities.conta_contabil import ContaContabil
from src.domain.models.entities.documento_fiscal import (
    DocumentoFiscal,
    ItemDocumentoFiscal,
)
from src.domain.models.entities.empresa import EmpresaOrigem
from src.domain.models.entities.participante import (
    ParticipanteDestino,
    ParticipanteOrigem,
)
from src.domain.models.entities.sped_registro import SpedRegistro

__all__ = [
    "ContaContabil",
    "DocumentoFiscal",
    "EmpresaOrigem",
    "ItemDocumentoFiscal",
    "ParticipanteDestino",
    "ParticipanteOrigem",
    "SpedRegistro",
]
