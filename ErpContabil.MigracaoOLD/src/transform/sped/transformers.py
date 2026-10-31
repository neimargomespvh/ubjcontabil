"""Transformers SPED → entidades do ERP (0150 → participante, 0500 → conta)."""
from __future__ import annotations

from src.domain.models.chunk import TransformResult
from src.domain.models.entities.conta_contabil import ContaContabil
from src.domain.models.entities.participante import ParticipanteDestino
from src.domain.models.entities.sped_registro import SpedRegistro
from src.transform.normalizers.normalizers import Normalizers
from src.transform.validators.cpf_cnpj import CpfCnpjValidator


def _campo(reg: SpedRegistro, i: int) -> str:
    """Retorna `campos[i]` ou string vazia, sem IndexError."""
    return reg.campos[i] if i < len(reg.campos) else ""


class SpedR0150ToParticipante:
    """Transforma um registro 0150 em ParticipanteDestino."""

    def transform(self, reg: SpedRegistro) -> TransformResult[ParticipanteDestino]:
        try:
            codigo = int(_campo(reg, 0) or 0)
        except ValueError:
            return TransformResult.falha(f"0150 código inválido: {_campo(reg, 0)!r}")

        cnpj = Normalizers.documento(_campo(reg, 3))
        cpf = Normalizers.documento(_campo(reg, 4))
        documento = cnpj or cpf or ""
        tipo = "JURIDICA" if cnpj else "FISICA"

        ok, motivo = CpfCnpjValidator.validar(documento, tipo)
        if not ok:
            return TransformResult.falha(motivo or "Documento inválido no 0150")

        return TransformResult.ok(ParticipanteDestino(
            codigo_origem=codigo,
            razao_social=Normalizers.texto(_campo(reg, 1)) or "(sem razão social)",
            nome_fantasia=None,
            documento=documento,
            tipo_pessoa=tipo,
            inscricao_estadual=Normalizers.documento(_campo(reg, 5)),
            municipio=Normalizers.texto(_campo(reg, 6)),
            uf=None,
            cep=None,
            email=None,
            telefone=None,
            origem_sistema="SPED",
        ))


class SpedR0500ToContaContabil:
    """Transforma um registro 0500 em ContaContabil."""

    def transform(self, reg: SpedRegistro) -> TransformResult[ContaContabil]:
        ind = _campo(reg, 2).strip().upper()
        natureza = "SINTETICA" if ind == "S" else "ANALITICA"

        codigo = _campo(reg, 4).strip()
        if not codigo:
            return TransformResult.falha("0500 sem COD_CTA")

        try:
            grau = int(_campo(reg, 3) or 1)
        except ValueError:
            grau = 1

        # Natureza de saldo: sintéticas não precisam; analíticas exigem D/C.
        # SPED 0500 não traz saldo — inferimos pelo primeiro dígito do código.
        natureza_saldo = None
        if natureza == "ANALITICA":
            primeiro = codigo.split(".")[0] if codigo else ""
            natureza_saldo = "DEVEDORA" if primeiro in ("1", "4", "5", "7") else "CREDORA"

        return TransformResult.ok(ContaContabil(
            codigo=codigo,
            nome=Normalizers.texto(_campo(reg, 5)) or codigo,
            codigo_pai=None,  # SPED não informa pai explicitamente
            natureza=natureza,
            grau=grau,
            natureza_saldo=natureza_saldo,
        ))
