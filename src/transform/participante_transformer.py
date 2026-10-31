"""Transformer participante origem → destino."""
from __future__ import annotations

from src.domain.contracts.transformer import IEntityTransformer
from src.domain.models.chunk import TransformResult
from src.domain.models.entities.participante import (
    ParticipanteDestino,
    ParticipanteOrigem,
)
from src.transform.mappings.fortes_para_erp_map import FortesParaErpMap
from src.transform.normalizers.normalizers import Normalizers
from src.transform.validators.cpf_cnpj import CpfCnpjValidator
from src.transform.validators.participante import ParticipanteValidator


class ParticipanteTransformer(
    IEntityTransformer[ParticipanteOrigem, ParticipanteDestino]
):
    """Aplica De-Para, normalizações e valida CPF/CNPJ."""

    def transform(
        self, origem: ParticipanteOrigem
    ) -> TransformResult[ParticipanteDestino]:
        tipo = FortesParaErpMap.tipo_pessoa(origem.tipo_pessoa)
        ok, motivo = CpfCnpjValidator.validar(origem.documento, tipo)
        if not ok:
            return TransformResult.falha(motivo or "Documento inválido")

        destino = ParticipanteDestino(
            codigo_origem=origem.codigo_origem,
            razao_social=Normalizers.texto(origem.razao_social) or "(sem razão social)",
            nome_fantasia=Normalizers.texto(origem.nome_fantasia),
            documento=CpfCnpjValidator.somente_digitos(origem.documento),
            tipo_pessoa=tipo,
            inscricao_estadual=Normalizers.documento(origem.inscricao_estadual),
            municipio=Normalizers.texto(origem.cidade),
            uf=Normalizers.uf(origem.uf),
            cep=Normalizers.documento(origem.cep),
            email=Normalizers.email(origem.email),
            telefone=Normalizers.telefone(origem.telefone),
            origem_sistema="FORTES",
        )
        ok, motivo = ParticipanteValidator.validar(destino)
        if not ok:
            return TransformResult.falha(motivo or "Falha de validação")
        return TransformResult.ok(destino)
