"""Extrator de movimentos SPED (C100 + C170) preservando vínculo documento→itens."""
from __future__ import annotations

import threading
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Union

from src.domain.contracts.extractor import IEntityExtractor
from src.domain.models.chunk import Chunk
from src.domain.models.entities.documento_fiscal import (
    DocumentoFiscal,
    ItemDocumentoFiscal,
)
from src.domain.models.entities.sped_registro import SpedRegistro
from src.transform.sped.parser import SpedLineParser
from src.transform.sped.transformers import (
    SpedRC100ToDocumentoFiscal,
    SpedRC170ToItemDocumentoFiscal,
    _documento_codigo_origem,
    _campo,
)

Movimento = Union[DocumentoFiscal, ItemDocumentoFiscal]


@dataclass(frozen=True, slots=True)
class _MovimentoChunkItem:
    """Wrapper interno — o pipeline usa DocumentoFiscal | ItemDocumentoFiscal diretamente."""


class SpedMovimentoExtractor(IEntityExtractor[Movimento]):
    """Lê SPED em ordem e emite C100 (documento) seguido de seus C170 (itens).

    Mantém o `codigo_origem` do último C100 válido para vincular os itens.
    Registros C100 cancelados (COD_SIT em 02, 03, 04, 05) ainda são emitidos
    para fins de auditoria.
    """

    def __init__(self, caminho: Path, tamanho_chunk: int = 2_000) -> None:
        self._caminho = caminho
        self._tamanho_chunk = tamanho_chunk
        self._tx_c100 = SpedRC100ToDocumentoFiscal()
        self._tx_c170_base = SpedRC170ToItemDocumentoFiscal()

    def extract(
        self, stop_event: threading.Event | None = None
    ) -> Iterator[Chunk[Movimento]]:
        lote: list[Movimento] = []
        total = 0
        ultimo_doc_origem = ""

        with self._caminho.open(encoding="utf-8", errors="replace") as f:
            for numero, linha in enumerate(f, start=1):
                if stop_event is not None and stop_event.is_set():
                    return

                raw = SpedLineParser.parse(linha)
                if raw is None or raw.codigo not in ("C100", "C170"):
                    continue

                reg = SpedRegistro(
                    codigo=raw.codigo,
                    campos=raw.campos,
                    linha_bruta=raw.linha_bruta,
                    arquivo=self._caminho.name,
                    numero_linha=numero,
                )

                if reg.codigo == "C100":
                    result = self._tx_c100.transform(reg)
                    if not result.sucesso or result.valor is None:
                        continue
                    doc = result.valor
                    ultimo_doc_origem = doc.codigo_origem
                    lote.append(doc)
                    total += 1
                else:  # C170
                    tx = self._tx_c170_base.com_documento(ultimo_doc_origem)
                    result = tx.transform(reg)
                    if not result.sucesso or result.valor is None:
                        continue
                    lote.append(result.valor)
                    total += 1

                if len(lote) >= self._tamanho_chunk:
                    yield Chunk(itens=lote, total_acumulado=total)
                    lote = []

        if lote:
            yield Chunk(itens=lote, total_acumulado=total)
