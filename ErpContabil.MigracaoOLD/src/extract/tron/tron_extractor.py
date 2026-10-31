"""Extrator genérico da Tron (Firebird), dirigido por arquivo de De-Para."""
from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.domain.models.chunk import Chunk
from src.domain.models.entities.conta_contabil import ContaContabil
from src.domain.models.entities.participante import ParticipanteOrigem
from src.extract.tron.firebird_extractor import TronConnectionOptions
from src.transform.normalizers.normalizers import Normalizers


@dataclass(frozen=True, slots=True)
class TronEntityConfig:
    """De-Para de uma entidade da Tron."""

    tabela: str
    campo_chave: str
    mapa: dict[str, str]


@dataclass(frozen=True, slots=True)
class TronConfig:
    entidades: dict[str, TronEntityConfig]

    @classmethod
    def from_file(cls, caminho: Path) -> TronConfig:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        return cls({
            nome: TronEntityConfig(
                tabela=cfg["tabela"],
                campo_chave=cfg["campo_chave"],
                mapa=cfg["mapa"],
            )
            for nome, cfg in dados["entidades"].items()
        })


class TronExtractor:
    """Extrai registros da Tron usando um TronConfig.

    Notas:
        - A chave primária da tabela deve ser monotônica para keyset pagination.
        - O mapa De-Para converte colunas da Tron → campos do nosso domínio.
        - Sufixo `_literal` indica que o valor vem direto do campo (ex.: "S"/"A"
          vira "SINTETICA"/"ANALITICA" via função de normalização).
    """

    def __init__(
        self,
        opt: TronConnectionOptions,
        config: TronConfig,
        tamanho_chunk: int = 5_000,
    ) -> None:
        self._opt = opt
        self._config = config
        self._tamanho_chunk = tamanho_chunk

    def _conectar(self) -> Any:
        from firebird.driver import connect

        dsn = f"{self._opt.host}/{self._opt.porta}:{self._opt.database}"
        return connect(
            dsn, user=self._opt.usuario, password=self._opt.senha,
            charset=self._opt.charset,
        )

    def _iterar(
        self, entidade: str, stop_event: threading.Event | None = None
    ) -> Iterator[tuple[dict[str, Any], int]]:
        cfg = self._config.entidades[entidade]
        colunas = ", ".join(cfg.mapa.keys())
        sql = (
            f"SELECT {colunas} FROM {cfg.tabela} "
            f"WHERE {cfg.campo_chave} > ? "
            f"ORDER BY {cfg.campo_chave}"
        )
        ultimo = 0
        conn = self._conectar()
        try:
            cur = conn.cursor()
            while True:
                if stop_event is not None and stop_event.is_set():
                    return
                cur.execute(sql, (ultimo,))
                rows = cur.fetchmany(self._tamanho_chunk)
                if not rows:
                    return
                for row in rows:
                    yield dict(zip(cfg.mapa.keys(), row, strict=True)), ultimo
                ultimo = int(rows[-1][list(cfg.mapa.keys()).index(cfg.campo_chave)])
                if len(rows) < self._tamanho_chunk:
                    return
        finally:
            conn.close()

    # -- públicas ------------------------------------------------------
    def extract_participantes(
        self, stop_event: threading.Event | None = None
    ) -> Iterator[Chunk[ParticipanteOrigem]]:
        lote: list[ParticipanteOrigem] = []
        total = 0
        for row, _ in self._iterar("participante", stop_event):
            lote.append(self._mapear_participante(row))
            total += 1
            if len(lote) >= self._tamanho_chunk:
                yield Chunk(itens=lote, total_acumulado=total)
                lote = []
        if lote:
            yield Chunk(itens=lote, total_acumulado=total)

    def extract_contas(
        self, stop_event: threading.Event | None = None
    ) -> Iterator[Chunk[ContaContabil]]:
        lote: list[ContaContabil] = []
        total = 0
        for row, _ in self._iterar("conta_contabil", stop_event):
            lote.append(self._mapear_conta(row))
            total += 1
            if len(lote) >= self._tamanho_chunk:
                yield Chunk(itens=lote, total_acumulado=total)
                lote = []
        if lote:
            yield Chunk(itens=lote, total_acumulado=total)

    # -- mappers ------------------------------------------------------
    @staticmethod
    def _mapear_participante(row: dict[str, Any]) -> ParticipanteOrigem:
        cnpj = Normalizers.documento(str(row.get("CNPJ") or ""))
        cpf = Normalizers.documento(str(row.get("CPF") or ""))
        tipo_lit = str(row.get("TIPO") or "").strip().upper()
        tipo = "FISICA" if tipo_lit in ("F", "PF", "FISICA") else "JURIDICA"
        return ParticipanteOrigem(
            codigo_origem=int(row["CODIGO"]),
            razao_social=row.get("NOME"),
            nome_fantasia=row.get("FANTASIA"),
            documento=cnpj or cpf or None,
            inscricao_estadual=row.get("INSCR_EST"),
            inscricao_municipal=None,
            endereco=None,
            cidade=row.get("CIDADE"),
            uf=row.get("UF"),
            cep=row.get("CEP"),
            email=row.get("EMAIL"),
            telefone=row.get("FONE"),
            tipo_pessoa=tipo,
        )

    @staticmethod
    def _mapear_conta(row: dict[str, Any]) -> ContaContabil:
        tipo = str(row.get("TIPO") or "").strip().upper()
        natureza = "SINTETICA" if tipo in ("S", "01", "1") else "ANALITICA"
        return ContaContabil(
            codigo=str(row["CODIGO"]),
            nome=str(row.get("DESCRICAO") or "(sem nome)"),
            codigo_pai=str(row.get("COD_PAI")) if row.get("COD_PAI") else None,
            natureza=natureza,
            grau=int(row.get("NIVEL") or 1),
            natureza_saldo=row.get("NATUREZA"),
        )
