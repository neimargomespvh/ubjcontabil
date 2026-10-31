"""Autenticação JWT + Basic, usuários em banco com roles, auditoria."""
from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Callable

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBasic,
    HTTPBasicCredentials,
    HTTPBearer,
    OAuth2PasswordRequestForm,
)
from pydantic import BaseModel, Field

from src.web.users import Role, UserRepository, Usuario, role_atende, verify_password

log = logging.getLogger("migracao.auth")

_JWT_SECRET = os.environ.get("JWT_SECRET", "")
_JWT_ALGO = "HS256"
_JWT_EXPIRE_MIN = int(os.environ.get("JWT_EXPIRE_MINUTES", "480"))
_CONNINFO = os.environ.get(
    "ERP_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/erp_contabil",
)

_basic = HTTPBasic(auto_error=False)
_bearer = HTTPBearer(auto_error=False)
_repo: UserRepository | None = None


def get_user_repo() -> UserRepository:
    global _repo
    if _repo is None:
        _repo = UserRepository(_CONNINFO)
        _repo.ensure_bootstrap_admin()
    return _repo


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str
    username: str


class TokenPayload(BaseModel):
    sub: str
    role: str
    uid: str
    exp: int
    iat: int


class CurrentUser(BaseModel):
    id: str
    username: str
    role: str
    nome: str | None = None


class UsuarioCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(default=Role.OPERADOR.value)
    nome: str | None = None


class UsuarioUpdate(BaseModel):
    role: str | None = None
    nome: str | None = None
    ativo: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UsuarioResponse(BaseModel):
    id: str
    username: str
    role: str
    nome: str | None
    ativo: bool
    criado_em: str | None = None
    ultimo_login: str | None = None


def _require_jwt_secret() -> None:
    if not _JWT_SECRET or len(_JWT_SECRET) < 32:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT_SECRET deve ter pelo menos 32 caracteres",
        )


def create_access_token(user: Usuario) -> TokenResponse:
    _require_jwt_secret()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=_JWT_EXPIRE_MIN)
    payload = {
        "sub": user.username,
        "role": user.role,
        "uid": user.id,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    token = jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGO)
    return TokenResponse(
        access_token=token,
        expires_in=_JWT_EXPIRE_MIN * 60,
        role=user.role,
        username=user.username,
    )


def decode_token(token: str) -> TokenPayload:
    _require_jwt_secret()
    try:
        data = jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGO])
        return TokenPayload(**data)
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def _authenticate(username: str, password: str) -> Usuario:
    repo = get_user_repo()
    found = repo.get_by_username(username)
    if found is None:
        # fallback legado: ADMIN_USER/ADMIN_PASSWORD só se tabela vazia
        env_user = os.environ.get("ADMIN_USER", "admin")
        env_pass = os.environ.get("ADMIN_PASSWORD", "")
        if (
            env_pass
            and secrets.compare_digest(username, env_user)
            and secrets.compare_digest(password, env_pass)
            and repo.count() == 0
        ):
            repo.ensure_bootstrap_admin()
            found = repo.get_by_username(username)
        if found is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciais inválidas",
                headers={"WWW-Authenticate": "Bearer"},
            )
    user, password_hash = found
    if not user.ativo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário desativado",
        )
    if not verify_password(password, password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    repo.touch_login(user.id)
    return user


def login_basic(
    creds: HTTPBasicCredentials | None = Depends(_basic),
) -> TokenResponse:
    """Login via HTTP Basic → JWT."""
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais obrigatórias",
            headers={"WWW-Authenticate": "Basic"},
        )
    user = _authenticate(str(creds.username), str(creds.password))
    log.info("Login OK: user=%s role=%s", user.username, user.role)
    return create_access_token(user)


def login_form(form: Annotated[OAuth2PasswordRequestForm, Depends()]) -> TokenResponse:
    """Login via form (username/password) → JWT — útil para Swagger/OAuth2."""
    user = _authenticate(form.username, form.password)
    log.info("Login form OK: user=%s role=%s", user.username, user.role)
    return create_access_token(user)


def get_current_user(
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
    basic: Annotated[HTTPBasicCredentials | None, Depends(_basic)] = None,
) -> CurrentUser:
    """Exige JWT (preferido) ou Basic (compat)."""
    if bearer and bearer.credentials:
        payload = decode_token(bearer.credentials)
        return CurrentUser(
            id=payload.uid,
            username=payload.sub,
            role=payload.role,
        )

    if basic is not None:
        user = _authenticate(str(basic.username), str(basic.password))
        return CurrentUser(
            id=user.id,
            username=user.username,
            role=user.role,
            nome=user.nome,
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Autenticação obrigatória (Bearer JWT ou Basic)",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_role(min_role: str) -> Callable[..., CurrentUser]:
    """Dependency factory: exige role mínima (admin > operador > leitura)."""

    def _dep(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
        if not role_atende(user.role, min_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permissão insuficiente (exige {min_role})",
            )
        return user

    return _dep


# Atalhos de dependency
RequireAdmin = Annotated[CurrentUser, Depends(require_role(Role.ADMIN.value))]
RequireOperador = Annotated[CurrentUser, Depends(require_role(Role.OPERADOR.value))]
RequireLeitura = Annotated[CurrentUser, Depends(require_role(Role.LEITURA.value))]

# Alias legado
verificar_admin = get_current_user


def audit(
    action: str,
    user: str,
    detail: str = "",
    request: Request | None = None,
) -> None:
    ip = "-"
    if request is not None:
        ip = request.client.host if request.client else "-"
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
    log.info(
        "AUDIT user=%s action=%s ip=%s detail=%s",
        user,
        action,
        ip,
        detail[:500] if detail else "-",
    )


def usuario_to_response(u: Usuario) -> UsuarioResponse:
    return UsuarioResponse(
        id=u.id,
        username=u.username,
        role=u.role,
        nome=u.nome,
        ativo=u.ativo,
        criado_em=u.criado_em.isoformat() if u.criado_em else None,
        ultimo_login=u.ultimo_login.isoformat() if u.ultimo_login else None,
    )
