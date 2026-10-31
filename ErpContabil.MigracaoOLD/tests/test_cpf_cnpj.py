"""Testes de validação de CPF/CNPJ."""
from __future__ import annotations

import pytest

from src.transform.validators.cpf_cnpj import CpfCnpjValidator


@pytest.mark.parametrize(
    "cpf",
    ["52998224725", "11144477735", "00000000191"],
)
def test_cpf_valido(cpf: str) -> None:
    """CPFs com DV correto devem retornar True."""
    assert CpfCnpjValidator.cpf_valido(cpf) is True


@pytest.mark.parametrize(
    "cnpj",
    ["11222333000181", "60746948000112"],
)
def test_cnpj_valido(cnpj: str) -> None:
    """CNPJs com DV correto devem retornar True."""
    assert CpfCnpjValidator.cnpj_valido(cnpj) is True


@pytest.mark.parametrize("invalido", ["11111111111", "", "abc"])
def test_cpf_invalido(invalido: str) -> None:
    """CPFs com DV errado ou formato inválido devem retornar False."""
    assert CpfCnpjValidator.cpf_valido(invalido) is False


@pytest.mark.parametrize("invalido", ["00000000000000", "", "xyz"])
def test_cnpj_invalido(invalido: str) -> None:
    """CNPJs com DV errado ou formato inválido devem retornar False."""
    assert CpfCnpjValidator.cnpj_valido(invalido) is False


def test_somente_digitos() -> None:
    """Máscaras devem ser removidas."""
    assert CpfCnpjValidator.somente_digitos("529.982.247-25") == "52998224725"
    assert CpfCnpjValidator.somente_digitos("11.222.333/0001-81") == "11222333000181"
    assert CpfCnpjValidator.somente_digitos(None) == ""
    assert CpfCnpjValidator.somente_digitos("abc") == ""


def test_validar_alto_nivel() -> None:
    """`validar()` deve retornar (ok, motivo)."""
    ok, motivo = CpfCnpjValidator.validar("529.982.247-25", "FISICA")
    assert ok is True
    assert motivo is None

    ok, motivo = CpfCnpjValidator.validar("11.222.333/0001-81", "JURIDICA")
    assert ok is True
    assert motivo is None

    ok, motivo = CpfCnpjValidator.validar("", "FISICA")
    assert ok is False
    assert motivo == "Documento vazio"

    ok, motivo = CpfCnpjValidator.validar("12345678901", "FISICA")
    assert ok is False
    assert motivo is not None and "CPF" in motivo
