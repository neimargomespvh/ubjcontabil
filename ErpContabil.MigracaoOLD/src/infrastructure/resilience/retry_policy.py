"""Política de retry com backoff exponencial."""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class RetryPolicy:
    """Executa uma função com tentativas e backoff exponencial."""

    def __init__(
        self,
        tentativas: int = 5,
        backoff_inicial_s: float = 1.0,
        fator: float = 2.0,
        max_backoff_s: float = 60.0,
    ) -> None:
        if tentativas < 1:
            raise ValueError("tentativas deve ser >= 1")
        self._tentativas = tentativas
        self._backoff_inicial_s = backoff_inicial_s
        self._fator = fator
        self._max_backoff_s = max_backoff_s

    def executar(self, fn: Callable[[], T]) -> T:
        """Executa `fn`; em caso de exceção, espera e tenta de novo."""
        ultimo: BaseException | None = None
        for tentativa in range(self._tentativas):
            try:
                return fn()
            except Exception as e:
                ultimo = e
                if tentativa == self._tentativas - 1:
                    break
                espera = min(
                    self._max_backoff_s,
                    self._backoff_inicial_s * (self._fator ** tentativa),
                )
                time.sleep(espera)
        assert ultimo is not None
        raise ultimo
