"""Extrator de registros a partir de arquivos .txt do SPED Fiscal/Contribuições."""
from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path

from src.domain.contracts.extractor import IEntityExtractor
from src.domain.models.chunk import Chunk
from src.domain.models.entities.sped_registro import SpedRegistro
from src.transform.sped.parser import SpedLineParser


class SpedTxtExtractor(IEntityExtractor[SpedRegistro]):
    """Lê um arquivo SPED e emite apenas os registros de cadastro relevantes.

    Notes:
        O e-Fisco Ceará não expõe API pública de download. O caminho realista é
        o cliente baixar os .txt do SPED no portal da Receita/SEFAZ e subir
        no painel. Nunca faça scraping/automação de login no e-CAC sem
        procuração eletrônica válida.
    """

    REGISTROS_INTERESSE: frozenset[str] = frozenset(
        {"0000", "0150", "0190", "0200", "0500", "C100", "C170"}
    )

    def __init__(self, caminho: Path, tamanho_chunk: int = 5_000) -> None:
        self._caminho = caminho
        self._tamanho_chunk = tamanho_chunk

    def extract(
        self, stop_event: threading.Event | None = None
    ) -> Iterator[Chunk[SpedRegistro]]:
        lote: list[SpedRegistro] = []
        total = 0
        with self._caminho.open(encoding="utf-8", errors="replace") as f:
            for numero, linha in enumerate(f, start=1):
                if stop_event is not None and stop_event.is_set():
                    return
                registro = SpedLineParser.parse(linha)
                if registro is None:
                    continue
                if registro.codigo not in self.REGISTROS_INTERESSE:
                    continue
                # enriquece com contexto de arquivo/linha
                registro = SpedRegistro(
                    codigo=registro.codigo,
                    campos=registro.campos,
                    linha_bruta=registro.linha_bruta,
                    arquivo=self._caminho.name,
                    numero_linha=numero,
                )
                lote.append(registro)
                total += 1
                if len(lote) >= self._tamanho_chunk:
                    yield Chunk(itens=lote, total_acumulado=total)
                    lote = []
        if lote:
            yield Chunk(itens=lote, total_acumulado=total)
