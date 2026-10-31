"""Autenticação HTTP Basic para o painel Admin."""
from __future__ import annotations

import os
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

_security = HTTPBasic(auto_error=False)


def verificar_admin(
    creds: HTTPBasicCredentials | None = Depends(_security),
) -> str:
    """Valida `ADMIN_USER` + `ADMIN_PASSWORD`. Falha fechada se env faltar."""
    usuario_esperado = os.environ.get("ADMIN_USER", "admin")
    senha_esperada = os.environ.get("ADMIN_PASSWORD", "")

    if not senha_esperada:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ADMIN_PASSWORD não configurada no servidor",
        )

    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação obrigatória",
            headers={"WWW-Authenticate": "Basic"},
        )

    ok_user = secrets.compare_digest(str(creds.username), usuario_esperado)
    ok_senha = secrets.compare_digest(str(creds.password), senha_esperada)
    if not (ok_user and ok_senha):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
            headers={"WWW-Authenticate": "Basic"},
        )
    return str(creds.username)
