"""Testes do parser de linhas SPED."""
from __future__ import annotations

import pytest

from src.transform.sped.parser import SpedLineParser


def test_parse_0150_valido() -> None:
    linha = "|0150|PART001|Fornecedor XYZ|1058|11222333000181||123456789|3550308|||Rua A|100|||"
    r = SpedLineParser.parse(linha)
    assert r is not None
    assert r.codigo == "0150"
    assert r.campos[0] == "PART001"
    assert r.campos[1] == "Fornecedor XYZ"


@pytest.mark.parametrize("invalida", ["", "0150|sem|pipe-inicial", "||"])
def test_parse_invalida(invalida: str) -> None:
    assert SpedLineParser.parse(invalida) is None


def test_parse_0000_valido() -> None:
    linha = "|0000|017|0|01012024|31122024|EMPRESA LTDA|12345678000199|CE|123456789||3550308|||A|1|"
    r = SpedLineParser.parse(linha)
    assert r is not None
    assert r.codigo == "0000"
    assert "EMPRESA LTDA" in r.campos
