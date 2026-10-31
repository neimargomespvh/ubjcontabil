"""Cliente HTTP para enviar lotes de eventos ao endpoint de sync na nuvem."""
from __future__ import annotations

from typing import Any

import httpx

from src.infrastructure.resilience.retry_policy import RetryPolicy


class DeltaClient:
    """Envia um lote de eventos para a API de sync na nuvem.

    Contrato esperado do servidor:
        POST {base_url}/api/sync/batch
        Authorization: Bearer {api_key}
        Body: {
            "lote_id": "...",
            "empresa_id": "...",
            "eventos": [
                {"entidade": "participante", "operacao": "UPSERT", "dados": {...}},
                {"entidade": "participante", "operacao": "DELETE", "registro_id": "123"}
            ]
        }
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout_s: float = 15.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout_s
        self._retry = RetryPolicy(tentativas=3, backoff_inicial_s=1.0)

    def enviar(self, lote: dict[str, Any]) -> bool:
        """Envia o lote; retorna True em 2xx. Retry exponencial em falhas."""
        url = f"{self._base_url}/api/sync/batch"
        headers = {"Authorization": f"Bearer {self._api_key}"}

        def _tentativa() -> bool:
            with httpx.Client(timeout=self._timeout) as client:
                r = client.post(url, json=lote, headers=headers)
            if r.status_code >= 500:
                raise RuntimeError(f"cloud 5xx: {r.status_code}")
            if r.status_code >= 400:
                raise httpx.HTTPStatusError(
                    f"cloud {r.status_code}: {r.text[:200]}",
                    request=r.request, response=r,
                )
            return True

        try:
            return self._retry.executar(_tentativa)
        except Exception:
            return False
