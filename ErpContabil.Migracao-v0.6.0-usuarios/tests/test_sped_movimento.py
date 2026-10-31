"""Testes dos transformers e parser de movimentos SPED (C100 / C170)."""
from __future__ import annotations

from decimal import Decimal

from src.domain.models.entities.sped_registro import SpedRegistro
from src.transform.sped.transformers import (
    SpedRC100ToDocumentoFiscal,
    SpedRC170ToItemDocumentoFiscal,
    _documento_codigo_origem,
)


def _reg(codigo: str, *campos: str) -> SpedRegistro:
    return SpedRegistro(
        codigo=codigo,
        campos=tuple(campos),
        linha_bruta="|" + "|".join((codigo,) + campos) + "|",
        arquivo="teste.txt",
        numero_linha=1,
    )


def test_c100_nfe_com_chave() -> None:
    # índices: IND_OPER IND_EMIT COD_PART COD_MOD COD_SIT SER NUM_DOC CHV_NFE DT_DOC DT_E_S VL_DOC ...
    chave = "23240112345678000199550010000001231123456789"
    reg = _reg(
        "C100",
        "1", "0", "PART01", "55", "00", "1", "123",
        chave, "15012024", "15012024", "1500.50",
        "0", "0.00", "0.00", "1400.00",
        "0", "0", "0", "0",
        "0", "180.00",  # VL_BC_ICMS / VL_ICMS approx positions
        "0", "0", "0", "10.00", "20.00", "30.00",
    )
    r = SpedRC100ToDocumentoFiscal().transform(reg)
    assert r.sucesso is True
    assert r.valor is not None
    assert r.valor.chave_nfe == chave
    assert r.valor.codigo_origem == chave
    assert r.valor.modelo == "55"
    assert r.valor.numero == "123"
    assert r.valor.ind_oper == "1"
    assert r.valor.valor_documento == Decimal("1500.50")


def test_c100_sem_chave_usa_modelo_serie_numero() -> None:
    reg = _reg(
        "C100",
        "0", "1", "P2", "01", "00", "U", "999",
        "", "01012024", "01012024", "100.00",
    )
    r = SpedRC100ToDocumentoFiscal().transform(reg)
    assert r.sucesso is True
    assert r.valor is not None
    assert r.valor.codigo_origem == "01|U|999"
    assert r.valor.chave_nfe == ""


def test_c100_sem_numero_nem_chave_falha() -> None:
    reg = _reg("C100", "1", "0", "P", "55", "00", "", "", "", "", "", "0")
    r = SpedRC100ToDocumentoFiscal().transform(reg)
    assert r.sucesso is False


def test_c170_basico() -> None:
    reg = _reg(
        "C170",
        "1", "PROD001", "Caneta azul", "10,000", "UN",
        "25.50", "0.00", "0", "000", "5102",
        "", "25.50", "18.00", "4.59",
    )
    tx = SpedRC170ToItemDocumentoFiscal("DOC-ORIGEM-1")
    r = tx.transform(reg)
    assert r.sucesso is True
    assert r.valor is not None
    assert r.valor.num_item == 1
    assert r.valor.cod_item == "PROD001"
    assert r.valor.quantidade == Decimal("10.000")
    assert r.valor.valor_item == Decimal("25.50")
    assert r.valor.cfop == "5102"
    assert r.valor.documento_codigo_origem == "DOC-ORIGEM-1"
    assert r.valor.codigo_origem == "DOC-ORIGEM-1#1"


def test_c170_num_item_invalido() -> None:
    reg = _reg("C170", "0", "X", "", "1", "UN", "1")
    r = SpedRC170ToItemDocumentoFiscal("D1").transform(reg)
    assert r.sucesso is False


def test_documento_codigo_origem_preferencia_chave() -> None:
    chave = "1" * 44
    assert _documento_codigo_origem(chave, "55", "1", "10") == chave
    assert _documento_codigo_origem("", "55", "1", "10") == "55|1|10"


def test_codigo_errado_rejeitado() -> None:
    reg = _reg("0150", "x")
    assert SpedRC100ToDocumentoFiscal().transform(reg).sucesso is False
    assert SpedRC170ToItemDocumentoFiscal().transform(reg).sucesso is False
