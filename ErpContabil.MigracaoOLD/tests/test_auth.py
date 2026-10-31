"""Testes de autenticação HTTP Basic do painel."""
from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient


def _basic(user: str, senha: str) -> dict[str, str]:
    token = base64.b64encode(f"{user}:{senha}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "senha-forte-123")
    # Recarrega o módulo após alterar env (o auth lê env em runtime, mas
    # queremos um TestClient limpo)
    from src.web.app import app
    return TestClient(app, raise_server_exceptions=False)


def test_health_publico(client: TestClient) -> None:
    r = client.get("/api/migracao/health")
    assert r.status_code == 200


def test_rota_protegida_sem_credenciais(client: TestClient) -> None:
    r = client.post("/api/migracao/fortes/testar", json={
        "host": "x", "database": "y", "usuario": "z", "senha": "w",
    })
    assert r.status_code == 401
    assert "WWW-Authenticate" in r.headers


def test_rota_protegida_senha_errada(client: TestClient) -> None:
    r = client.post(
        "/api/migracao/fortes/testar",
        json={"host": "x", "database": "y", "usuario": "z", "senha": "w"},
        headers=_basic("admin", "senha-errada"),
    )
    assert r.status_code == 401


def test_admin_sem_env_falha_fechado(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    r = client.post(
        "/api/migracao/fortes/testar",
        json={"host": "x", "database": "y", "usuario": "z", "senha": "w"},
        headers=_basic("admin", "qualquer"),
    )
    assert r.status_code == 500
