"""Testes de autenticação JWT + roles (com mocks de repositório quando necessário)."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.web.users import Role, Usuario


def _basic(user: str, senha: str) -> dict[str, str]:
    token = base64.b64encode(f"{user}:{senha}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


@pytest.fixture
def admin_user() -> Usuario:
    return Usuario(
        id="00000000-0000-0000-0000-000000000001",
        username="admin",
        role=Role.ADMIN.value,
        nome="Admin",
        ativo=True,
        criado_em=datetime.now(timezone.utc),
    )


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, admin_user: Usuario) -> TestClient:
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "senha-forte-123")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-at-least-32-characters-long")
    monkeypatch.setenv(
        "ERP_DATABASE_URL", "postgresql://erp:erp@localhost:5432/erp_contabil"
    )

    from src.web.users import hash_password

    ph = hash_password("senha-forte-123")

    mock_repo = MagicMock()
    mock_repo.count.return_value = 1
    mock_repo.get_by_username.side_effect = lambda u: (
        (admin_user, ph) if u == "admin" else None
    )
    mock_repo.get_by_id.return_value = admin_user
    mock_repo.list_all.return_value = [admin_user]
    mock_repo.ensure_bootstrap_admin.return_value = None
    mock_repo.touch_login.return_value = None

    import src.web.auth as auth_mod

    monkeypatch.setattr(auth_mod, "_repo", mock_repo)
    monkeypatch.setattr(auth_mod, "get_user_repo", lambda: mock_repo)

    from src.web.app import app

    return TestClient(app, raise_server_exceptions=False)


def test_health_publico(client: TestClient) -> None:
    r = client.get("/api/migracao/health")
    assert r.status_code == 200


def test_rota_protegida_sem_credenciais(client: TestClient) -> None:
    r = client.get("/api/migracao/jobs")
    assert r.status_code == 401


def test_login_emite_jwt(client: TestClient) -> None:
    r = client.post("/api/auth/login", headers=_basic("admin", "senha-forte-123"))
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["role"] == "admin"
    assert body["username"] == "admin"


def test_acesso_com_jwt(client: TestClient) -> None:
    login = client.post("/api/auth/login", headers=_basic("admin", "senha-forte-123"))
    assert login.status_code == 200
    token = login.json()["access_token"]
    r = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["username"] == "admin"


def test_senha_errada(client: TestClient) -> None:
    r = client.post("/api/auth/login", headers=_basic("admin", "errada"))
    assert r.status_code == 401
