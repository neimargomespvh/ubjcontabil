"""Transactional Outbox para o Sincronizador Delta."""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.domain.enums.enums import OperacaoSync

if TYPE_CHECKING:
    from psycopg import Connection


_INSERT_SQL = """
    INSERT INTO sync.sync_outbox (empresa_id, entidade, operacao, registro_id)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (empresa_id, entidade, registro_id)
        WHERE sincronizado_em IS NULL
    DO UPDATE SET operacao = EXCLUDED.operacao,
                  agendado_para = now(),
                  tentativas = 0
"""


class SyncOutboxWriter:
    """Enfileira eventos na MESMA transação do Load.

    Notes:
        - Um evento por registro (não por lote).
        - Coalesce: se já há evento pendente, atualiza a operação — evita
          duplicar UPSERT+DELETE do mesmo registro em lotes consecutivos.
    """

    def enfileirar_batch(
        self,
        conn: Connection,
        empresa_id: str,
        entidade: str,
        registro_ids: list[str],
        operacao: OperacaoSync,
    ) -> int:
        if not registro_ids:
            return 0
        with conn.cursor() as cur:
            cur.executemany(
                _INSERT_SQL,
                [(empresa_id, entidade, operacao.value, rid) for rid in registro_ids],
            )
        return len(registro_ids)
