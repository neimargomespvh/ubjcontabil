"""Logger resiliente (JSONL + tabela migracao.erro)."""
from __future__ import annotations

import json
import socket
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg

from src.domain.models.migration_result import MigrationResult


class MigrationLogger:
    """Grava cada erro em arquivo JSONL e (best-effort) na tabela migracao.erro.

    Notes:
        - Thread-safe via `threading.Lock` — o arquivo é a fonte de auditoria.
        - Se o INSERT no banco falhar, o erro JÁ está no arquivo (nunca perde).
        - Abre/fecha conexão por erro: erros são raros, simplicidade vence.
    """

    def __init__(self, caminho_log: Path, connection_string: str) -> None:
        self._caminho_log = caminho_log
        self._connection_string = connection_string
        self._lock = threading.Lock()

    def iniciar_job(self, job_id: str, origem: str) -> None:
        """Registra o início do job no arquivo e em migracao.job."""
        self._escrever({
            "evento": "inicio_job", "job_id": job_id, "origem": origem,
            "ts": datetime.now(UTC).isoformat(),
            "maquina": socket.gethostname(),
        })
        self._executar_sql(
            "INSERT INTO migracao.job (id, origem) VALUES (%s, %s) "
            "ON CONFLICT (id) DO NOTHING",
            (job_id, origem),
        )

    def erro(
        self,
        entidade: str,
        registro_id: str,
        mensagem: str,
        excecao: BaseException | None = None,
    ) -> None:
        """Grava linha JSONL + INSERT em migracao.erro."""
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "entidade": entidade,
            "registro_id": registro_id,
            "mensagem": mensagem,
            "stack": str(excecao) if excecao else None,
            "maquina": socket.gethostname(),
        }
        self._escrever(payload)
        self._executar_sql(
            "INSERT INTO migracao.erro (entidade, registro_id, mensagem, stack) "
            "VALUES (%s, %s, %s, %s)",
            (entidade, registro_id, mensagem, payload["stack"]),
        )

    def finalizar_job(self, job_id: str, resultado: MigrationResult) -> None:
        """Marca o job como concluído em migracao.job e no arquivo."""
        self._escrever({
            "evento": "fim_job", "job_id": job_id,
            "sucesso": resultado.sucesso, "status": resultado.status.value,
            "importados": resultado.importados, "erros": resultado.erros,
            "duracao_s": resultado.duracao_segundos,
        })
        self._executar_sql(
            "UPDATE migracao.job SET finalizado_em = now(), sucesso = %s, "
            "importados = %s, erros = %s, duracao_s = %s WHERE id = %s",
            (resultado.sucesso, resultado.importados, resultado.erros,
             resultado.duracao_segundos, job_id),
        )

    # -- internos -----------------------------------------------------
    def _escrever(self, payload: dict[str, Any]) -> None:
        linha = json.dumps(payload, ensure_ascii=False) + "\n"
        with self._lock:
            self._caminho_log.parent.mkdir(parents=True, exist_ok=True)
            with self._caminho_log.open("a", encoding="utf-8") as f:
                f.write(linha)

    def _executar_sql(self, sql: str, params: tuple[Any, ...]) -> None:
        try:
            with (
                psycopg.connect(self._connection_string, autocommit=True) as conn,
                conn.cursor() as cur,
            ):
                cur.execute(sql, params)
        except Exception:
            pass  # arquivo já tem o registro — auditoria preservada
