"""Descoberta de schema do Firebird da Tron (cache em JSON)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.extract.tron.firebird_extractor import TronConnectionOptions


@dataclass(frozen=True, slots=True)
class TronColuna:
    tabela: str
    coluna: str
    tipo: str
    tamanho: int | None
    nulavel: bool


class TronSchemaDiscovery:
    """Lê INFORMATION_SCHEMA do Firebird e salva um snapshot em JSON.

    Uso típico (primeira execução contra um cliente novo):
        disc = TronSchemaDiscovery(opt)
        disc.salvar_snapshot(Path("configs/tron_schema_real.json"))

    Depois, use o JSON como referência para preencher `tron_map.json`.
    """

    _SQL = """
        SELECT TRIM(r.RDB$RELATION_NAME)  AS tabela,
               TRIM(f.RDB$FIELD_NAME)    AS coluna,
               CASE f.RDB$FIELD_TYPE
                    WHEN 7  THEN 'SMALLINT'
                    WHEN 8  THEN 'INTEGER'
                    WHEN 12 THEN 'DATE'
                    WHEN 13 THEN 'TIME'
                    WHEN 16 THEN 'BIGINT'
                    WHEN 27 THEN 'DOUBLE'
                    WHEN 35 THEN 'TIMESTAMP'
                    WHEN 37 THEN 'VARCHAR'
                    WHEN 261 THEN 'BLOB'
                    ELSE 'OUTRO'
               END AS tipo,
               f.RDB$CHARACTER_LENGTH AS tamanho,
               CASE WHEN f.RDB$NULL_FLAG = 1 THEN 0 ELSE 1 END AS nulavel
        FROM RDB$RELATION_FIELDS f
        JOIN RDB$RELATIONS r ON r.RDB$RELATION_NAME = f.RDB$RELATION_NAME
        WHERE r.RDB$SYSTEM_FLAG = 0
        ORDER BY r.RDB$RELATION_NAME, f.RDB$FIELD_POSITION
    """

    def __init__(self, opt: TronConnectionOptions) -> None:
        self._opt = opt

    def descobrir(self) -> list[TronColuna]:
        from firebird.driver import connect

        dsn = f"{self._opt.host}/{self._opt.porta}:{self._opt.database}"
        conn = connect(
            dsn, user=self._opt.usuario, password=self._opt.senha,
            charset=self._opt.charset,
        )
        try:
            cur = conn.cursor()
            cur.execute(self._SQL)
            return [
                TronColuna(
                    tabela=str(r[0]).strip(),
                    coluna=str(r[1]).strip(),
                    tipo=str(r[2]),
                    tamanho=int(r[3]) if r[3] is not None else None,
                    nulavel=bool(r[4]),
                )
                for r in cur.fetchall()
            ]
        finally:
            conn.close()

    def salvar_snapshot(self, destino: Path) -> int:
        """Serializa o schema em JSON. Retorna o número de colunas."""
        colunas = self.descobrir()
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(
            json.dumps([asdict(c) for c in colunas], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return len(colunas)


def carregar_snapshot(caminho: Path) -> dict[str, list[TronColuna]]:
    """Carrega o snapshot e agrupa por tabela."""
    dados: list[dict[str, Any]] = json.loads(caminho.read_text(encoding="utf-8"))
    por_tabela: dict[str, list[TronColuna]] = {}
    for d in dados:
        por_tabela.setdefault(d["tabela"], []).append(TronColuna(**d))
    return por_tabela
