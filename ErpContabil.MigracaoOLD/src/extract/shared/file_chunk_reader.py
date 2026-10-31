"""Leitura de arquivos grandes em chunks de linhas."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path


class FileChunkReader:
    """Lê um arquivo de texto em lotes de N linhas."""

    def __init__(self, tamanho_chunk: int = 5_000, encoding: str = "utf-8") -> None:
        self._tamanho_chunk = tamanho_chunk
        self._encoding = encoding

    def ler(self, caminho: Path) -> Iterator[list[str]]:
        lote: list[str] = []
        with caminho.open(encoding=self._encoding, errors="replace") as f:
            for linha in f:
                lote.append(linha.rstrip("\r\n"))
                if len(lote) >= self._tamanho_chunk:
                    yield lote
                    lote = []
        if lote:
            yield lote
