"""Testes da política de retry."""
from __future__ import annotations

import pytest

from src.infrastructure.resilience.retry_policy import RetryPolicy


def test_retry_sucesso_imediato() -> None:
    chamadas = {"n": 0}

    def fn() -> str:
        chamadas["n"] += 1
        return "ok"

    policy = RetryPolicy(tentativas=3, backoff_inicial_s=0.01)
    assert policy.executar(fn) == "ok"
    assert chamadas["n"] == 1


def test_retry_recupera_apos_falhas() -> None:
    chamadas = {"n": 0}

    def fn() -> str:
        chamadas["n"] += 1
        if chamadas["n"] < 3:
            raise RuntimeError("flaky")
        return "ok"

    policy = RetryPolicy(tentativas=5, backoff_inicial_s=0.01)
    assert policy.executar(fn) == "ok"
    assert chamadas["n"] == 3


def test_retry_esgota() -> None:
    policy = RetryPolicy(tentativas=3, backoff_inicial_s=0.01)

    def sempre_falha() -> str:
        raise RuntimeError("sempre")

    with pytest.raises(RuntimeError, match="sempre"):
        policy.executar(sempre_falha)
