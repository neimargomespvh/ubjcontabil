"""Validação de participantes antes do load."""
from __future__ import annotations

from src.domain.models.entities.participante import ParticipanteDestino


class ParticipanteValidator:
    """Regras de negócio sobre um participante já normalizado."""

    @staticmethod
    def validar(p: ParticipanteDestino) -> tuple[bool, str | None]:
        """Valida razão social, documento e UF."""
        if not p.razao_social or not p.razao_social.strip():
            return False, "Razão social vazia"
        if not p.documento or len(p.documento) not in (11, 14):
            return False, f"Documento com tamanho inválido ({len(p.documento or '')})"
        if p.uf is not None and len(p.uf) != 2:
            return False, f"UF inválida: {p.uf!r}"
        return True, None
