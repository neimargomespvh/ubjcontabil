"""Testes da validação contábil do plano de contas."""
from __future__ import annotations

from src.domain.models.entities.conta_contabil import ContaContabil
from src.transform.validators.plano_contas import PlanoContasValidator


def _conta(
    codigo: str,
    pai: str | None,
    nat: str,
    grau: int,
    saldo: str | None = None,
) -> ContaContabil:
    return ContaContabil(
        codigo=codigo,
        nome=f"Conta {codigo}",
        codigo_pai=pai,
        natureza=nat,
        grau=grau,
        natureza_saldo=saldo,
    )


def test_plano_valido() -> None:
    """Plano bem formado (sintética → analítica) deve passar."""
    contas = [
        _conta("1", None, "SINTETICA", 1),
        _conta("1.1", "1", "ANALITICA", 2, "DEVEDORA"),
    ]
    resultado = PlanoContasValidator.validar(contas)
    assert resultado.valido is True
    assert resultado.erros == []


def test_sintetica_sem_filhos_falha() -> None:
    """Sintética sem filhos deve retornar inválido."""
    contas = [_conta("1", None, "SINTETICA", 1)]
    resultado = PlanoContasValidator.validar(contas)
    assert resultado.valido is False
    assert any("sint" in e.lower() for e in resultado.erros)


def test_ciclo_falha() -> None:
    """Ciclo A→B→A deve retornar inválido."""
    contas = [
        _conta("1", "2", "SINTETICA", 2),
        _conta("2", "1", "SINTETICA", 2),
    ]
    resultado = PlanoContasValidator.validar(contas)
    assert resultado.valido is False
    assert any("ciclo" in e.lower() for e in resultado.erros)


def test_pai_inexistente_falha() -> None:
    """Codigo_pai que não existe na lista deve ser reportado."""
    contas = [_conta("1.1", "9.9", "ANALITICA", 2, "DEVEDORA")]
    resultado = PlanoContasValidator.validar(contas)
    assert resultado.valido is False
    assert any("inexistente" in e.lower() for e in resultado.erros)


def test_analitica_sem_natureza_saldo_falha() -> None:
    """Analítica sem natureza de saldo deve falhar."""
    contas = [
        _conta("1", None, "SINTETICA", 1),
        _conta("1.1", "1", "ANALITICA", 2),   # sem saldo
    ]
    resultado = PlanoContasValidator.validar(contas)
    assert resultado.valido is False
    assert any("saldo" in e.lower() for e in resultado.erros)
