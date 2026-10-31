"""Transformers SPED → entidades do ERP.

Cobertura:
  - 0150 → ParticipanteDestino
  - 0500 → ContaContabil
  - C100 → DocumentoFiscal (cabeçalho NF / documento)
  - C170 → ItemDocumentoFiscal (itens)

Layouts conforme Guia Prático EFD ICMS/IPI (campos após o código do registro).
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from src.domain.models.chunk import TransformResult
from src.domain.models.entities.conta_contabil import ContaContabil
from src.domain.models.entities.documento_fiscal import (
    DocumentoFiscal,
    ItemDocumentoFiscal,
)
from src.domain.models.entities.participante import ParticipanteDestino
from src.domain.models.entities.sped_registro import SpedRegistro
from src.transform.normalizers.normalizers import Normalizers
from src.transform.validators.cpf_cnpj import CpfCnpjValidator


def _campo(reg: SpedRegistro, i: int) -> str:
    """Retorna `campos[i]` ou string vazia, sem IndexError."""
    return reg.campos[i] if i < len(reg.campos) else ""


def _decimal(valor: str, default: str = "0") -> Decimal:
    """Converte string SPED (vírgula ou ponto) em Decimal."""
    s = (valor or default).strip().replace(",", ".")
    if not s:
        s = default
    try:
        return Decimal(s)
    except InvalidOperation:
        return Decimal(default)


def _documento_codigo_origem(
    chave_nfe: str, modelo: str, serie: str, numero: str
) -> str:
    """Gera identificador estável do documento para upsert/outbox."""
    chave = (chave_nfe or "").strip()
    if len(chave) == 44 and chave.isdigit():
        return chave
    return f"{modelo}|{serie}|{numero}"


class SpedR0150ToParticipante:
    """Transforma um registro 0150 em ParticipanteDestino."""

    def transform(self, reg: SpedRegistro) -> TransformResult[ParticipanteDestino]:
        if reg.codigo != "0150":
            return TransformResult.falha(f"Esperado 0150, recebido {reg.codigo}")

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

        return TransformResult.ok(
            ParticipanteDestino(
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
            )
        )


class SpedR0500ToContaContabil:
    """Transforma um registro 0500 em ContaContabil."""

    def transform(self, reg: SpedRegistro) -> TransformResult[ContaContabil]:
        if reg.codigo != "0500":
            return TransformResult.falha(f"Esperado 0500, recebido {reg.codigo}")

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
            natureza_saldo = (
                "DEVEDORA" if primeiro in ("1", "4", "5", "7") else "CREDORA"
            )

        return TransformResult.ok(
            ContaContabil(
                codigo=codigo,
                nome=Normalizers.texto(_campo(reg, 5)) or codigo,
                codigo_pai=None,
                natureza=natureza,
                grau=grau,
                natureza_saldo=natureza_saldo,
            )
        )


class SpedRC100ToDocumentoFiscal:
    """Transforma um registro C100 em DocumentoFiscal.

    Layout (índices em `campos`):
      0 IND_OPER | 1 IND_EMIT | 2 COD_PART | 3 COD_MOD | 4 COD_SIT
      5 SER | 6 NUM_DOC | 7 CHV_NFE | 8 DT_DOC | 9 DT_E_S
      10 VL_DOC | 11 IND_PGTO | 12 VL_DESC | 13 VL_ABAT_NT | 14 VL_MERC
      ... 20 VL_ICMS ... 24 VL_IPI | 25 VL_PIS | 26 VL_COFINS
    """

    def transform(self, reg: SpedRegistro) -> TransformResult[DocumentoFiscal]:
        if reg.codigo != "C100":
            return TransformResult.falha(f"Esperado C100, recebido {reg.codigo}")

        modelo = _campo(reg, 3).strip()
        serie = _campo(reg, 5).strip()
        numero = _campo(reg, 6).strip()
        chave = _campo(reg, 7).strip()

        if not numero and not chave:
            return TransformResult.falha("C100 sem NUM_DOC e sem CHV_NFE")

        cod_sit = _campo(reg, 4).strip() or "00"
        # Documentos cancelados / denegados ainda são importados (auditoria)
        # mas marcamos a situação.

        codigo_origem = _documento_codigo_origem(chave, modelo, serie, numero)

        return TransformResult.ok(
            DocumentoFiscal(
                chave_nfe=chave,
                numero=numero or chave[-9:] if len(chave) >= 9 else numero,
                serie=serie,
                modelo=modelo or "55",
                data_emissao=_campo(reg, 8).strip(),
                data_entrada_saida=_campo(reg, 9).strip(),
                ind_oper=_campo(reg, 0).strip() or "0",
                ind_emit=_campo(reg, 1).strip() or "0",
                cod_part=_campo(reg, 2).strip(),
                cod_sit=cod_sit,
                valor_documento=_decimal(_campo(reg, 10)),
                valor_mercadoria=_decimal(_campo(reg, 14)),
                valor_desconto=_decimal(_campo(reg, 12)),
                valor_icms=_decimal(_campo(reg, 20)),
                valor_ipi=_decimal(_campo(reg, 24)),
                valor_pis=_decimal(_campo(reg, 25)),
                valor_cofins=_decimal(_campo(reg, 26)),
                origem_sistema="SPED",
                codigo_origem=codigo_origem,
            )
        )


class SpedRC170ToItemDocumentoFiscal:
    """Transforma um registro C170 em ItemDocumentoFiscal.

    O vínculo com o C100 pai é feito via `documento_codigo_origem`, que deve
    ser injetado pelo orquestrador/contexto de leitura (último C100 visto).

    Layout (índices):
      0 NUM_ITEM | 1 COD_ITEM | 2 DESCR_COMPL | 3 QTD | 4 UNID
      5 VL_ITEM | 6 VL_DESC | 7 IND_MOV | 8 CST_ICMS | 9 CFOP
      10 COD_NAT | 11 VL_BC_ICMS | 12 ALIQ_ICMS | 13 VL_ICMS | ...
    """

    def __init__(self, documento_codigo_origem: str = "") -> None:
        self._doc_origem = documento_codigo_origem

    def com_documento(self, codigo_origem: str) -> SpedRC170ToItemDocumentoFiscal:
        """Retorna nova instância vinculada ao documento pai."""
        return SpedRC170ToItemDocumentoFiscal(documento_codigo_origem=codigo_origem)

    def transform(self, reg: SpedRegistro) -> TransformResult[ItemDocumentoFiscal]:
        if reg.codigo != "C170":
            return TransformResult.falha(f"Esperado C170, recebido {reg.codigo}")

        try:
            num_item = int(_campo(reg, 0) or 0)
        except ValueError:
            return TransformResult.falha(f"C170 NUM_ITEM inválido: {_campo(reg, 0)!r}")

        if num_item <= 0:
            return TransformResult.falha("C170 NUM_ITEM deve ser > 0")

        cod_item = _campo(reg, 1).strip()
        if not cod_item:
            return TransformResult.falha("C170 sem COD_ITEM")

        doc_origem = self._doc_origem
        if not doc_origem:
            # Fallback: ainda grava, mas o vínculo fica fraco
            doc_origem = f"UNKNOWN#{reg.arquivo}#{reg.numero_linha}"

        codigo_origem = f"{doc_origem}#{num_item}"

        return TransformResult.ok(
            ItemDocumentoFiscal(
                num_item=num_item,
                cod_item=cod_item,
                descricao=Normalizers.texto(_campo(reg, 2)),
                quantidade=_decimal(_campo(reg, 3), "0"),
                unidade=Normalizers.texto(_campo(reg, 4)),
                valor_item=_decimal(_campo(reg, 5)),
                valor_desconto=_decimal(_campo(reg, 6)),
                cfop=_campo(reg, 9).strip(),
                cst_icms=_campo(reg, 8).strip(),
                valor_bc_icms=_decimal(_campo(reg, 11)),
                aliquota_icms=_decimal(_campo(reg, 12)),
                valor_icms=_decimal(_campo(reg, 13)),
                documento_codigo_origem=doc_origem,
                origem_sistema="SPED",
                codigo_origem=codigo_origem,
            )
        )
