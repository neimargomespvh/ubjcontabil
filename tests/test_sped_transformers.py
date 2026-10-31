"""Testes dos transformers SPED → ERP."""
from __future__ import annotations

from src.domain.models.entities.sped_registro import SpedRegistro
from src.transform.sped.transformers import (
    SpedR0150ToParticipante,
    SpedR0500ToContaContabil,
)


def _reg(codigo: str, *campos: str) -> SpedRegistro:
    return SpedRegistro(codigo=codigo, campos=tuple(campos), linha_bruta="|x|")


def test_0150_pj_valido() -> None:
    reg = _reg("0150", "P001", "Fornecedor XYZ", "1058",
               "11222333000181", "", "123456789", "3550308")
    r = SpedR0150ToParticipante().transform(reg)
    assert r.sucesso is True
    assert r.valor is not None
    assert r.valor.razao_social == "Fornecedor XYZ"
    assert r.valor.documento == "11222333000181"
    assert r.valor.tipo_pessoa == "JURIDICA"
    assert r.valor.origem_sistema == "SPED"


def test_0150_pf_valido() -> None:
    reg = _reg("0150", "P002", "João da Silva", "1058",
               "", "52998224725", "", "")
    r = SpedR0150ToParticipante().transform(reg)
    assert r.sucesso is True
    assert r.valor is not None
    assert r.valor.documento == "52998224725"
    assert r.valor.tipo_pessoa == "FISICA"


def test_0150_documento_invalido() -> None:
    reg = _reg("0150", "P003", "Empresa Ruim", "1058",
               "00000000000000", "", "", "")
    r = SpedR0150ToParticipante().transform(reg)
    assert r.sucesso is False
    assert r.motivo is not None and "CNPJ" in r.motivo


def test_0500_sintetica() -> None:
    # DT_ALT, COD_NAT_CC, IND_CTA, NIVEL, COD_CTA, NOME_CTA
    reg = _reg("0500", "01012024", "01", "S", "1", "1", "ATIVO")
    r = SpedR0500ToContaContabil().transform(reg)
    assert r.sucesso is True
    assert r.valor is not None
    assert r.valor.natureza == "SINTETICA"
    assert r.valor.codigo == "1"
    assert r.valor.grau == 1


def test_0500_analitica() -> None:
    reg = _reg("0500", "01012024", "01", "A", "4", "1.1.01.001", "CAIXA")
    r = SpedR0500ToContaContabil().transform(reg)
    assert r.sucesso is True
    assert r.valor is not None
    assert r.valor.natureza == "ANALITICA"
    assert r.valor.natureza_saldo == "DEVEDORA"  # código "1.x" = ativo


def test_0500_sem_codigo_falha() -> None:
    reg = _reg("0500", "01012024", "01", "A", "4", "", "SEM CÓDIGO")
    r = SpedR0500ToContaContabil().transform(reg)
    assert r.sucesso is False
    assert r.motivo is not None and "COD_CTA" in r.motivo
