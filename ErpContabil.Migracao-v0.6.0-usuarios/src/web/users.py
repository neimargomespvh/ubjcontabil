"""Repositório e modelos de usuários do painel (roles)."""
from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

import psycopg
from passlib.context import CryptContext

log = logging.getLogger("migracao.users")

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Role(StrEnum):
    ADMIN = "admin"
    OPERADOR = "operador"
    LEITURA = "leitura"


# Hierarquia: admin > operador > leitura
_ROLE_RANK: dict[str, int] = {
    Role.LEITURA: 1,
    Role.OPERADOR: 2,
    Role.ADMIN: 3,
}


@dataclass(slots=True)
class Usuario:
    id: str
    username: str
    role: str
    nome: str | None
    ativo: bool
    criado_em: datetime | None = None
    ultimo_login: datetime | None = None


def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, password_hash: str) -> bool:
    try:
        return _pwd.verify(plain, password_hash)
    except Exception:
        return False


def role_atende(role_usuario: str, role_minima: str) -> bool:
    return _ROLE_RANK.get(role_usuario, 0) >= _ROLE_RANK.get(role_minima, 99)


class UserRepository:
    """CRUD de usuários em migracao.usuario."""

    def __init__(self, conninfo: str) -> None:
        self._conninfo = conninfo

    def count(self) -> int:
        with psycopg.connect(self._conninfo, autocommit=True) as conn:
            row = conn.execute("SELECT COUNT(*) FROM migracao.usuario").fetchone()
            return int(row[0]) if row else 0

    def get_by_username(self, username: str) -> tuple[Usuario, str] | None:
        """Retorna (Usuario, password_hash) ou None."""
        with psycopg.connect(self._conninfo, autocommit=True) as conn:
            row = conn.execute(
                """
                SELECT id::text, username, password_hash, role, nome, ativo,
                       criado_em, ultimo_login
                FROM migracao.usuario
                WHERE username = %s
                """,
                (username,),
            ).fetchone()
        if not row:
            return None
        u = Usuario(
            id=row[0],
            username=row[1],
            role=row[3],
            nome=row[4],
            ativo=bool(row[5]),
            criado_em=row[6],
            ultimo_login=row[7],
        )
        return u, row[2]

    def get_by_id(self, user_id: str) -> Usuario | None:
        with psycopg.connect(self._conninfo, autocommit=True) as conn:
            row = conn.execute(
                """
                SELECT id::text, username, role, nome, ativo, criado_em, ultimo_login
                FROM migracao.usuario WHERE id = %s::uuid
                """,
                (user_id,),
            ).fetchone()
        if not row:
            return None
        return Usuario(
            id=row[0], username=row[1], role=row[2], nome=row[3],
            ativo=bool(row[4]), criado_em=row[5], ultimo_login=row[6],
        )

    def list_all(self) -> list[Usuario]:
        with psycopg.connect(self._conninfo, autocommit=True) as conn:
            rows = conn.execute(
                """
                SELECT id::text, username, role, nome, ativo, criado_em, ultimo_login
                FROM migracao.usuario
                ORDER BY username
                """
            ).fetchall()
        return [
            Usuario(
                id=r[0], username=r[1], role=r[2], nome=r[3],
                ativo=bool(r[4]), criado_em=r[5], ultimo_login=r[6],
            )
            for r in rows
        ]

    def create(
        self,
        username: str,
        password: str,
        role: str,
        nome: str | None = None,
    ) -> Usuario:
        if role not in {r.value for r in Role}:
            raise ValueError(f"Role inválida: {role}")
        uid = str(uuid.uuid4())
        ph = hash_password(password)
        with psycopg.connect(self._conninfo) as conn:
            conn.execute(
                """
                INSERT INTO migracao.usuario (id, username, password_hash, role, nome)
                VALUES (%s::uuid, %s, %s, %s, %s)
                """,
                (uid, username, ph, role, nome),
            )
            conn.commit()
        u = self.get_by_id(uid)
        assert u is not None
        return u

    def update(
        self,
        user_id: str,
        *,
        role: str | None = None,
        nome: str | None = None,
        ativo: bool | None = None,
        password: str | None = None,
    ) -> Usuario:
        sets: list[str] = ["atualizado_em = now()"]
        params: list[Any] = []
        if role is not None:
            if role not in {r.value for r in Role}:
                raise ValueError(f"Role inválida: {role}")
            sets.append("role = %s")
            params.append(role)
        if nome is not None:
            sets.append("nome = %s")
            params.append(nome)
        if ativo is not None:
            sets.append("ativo = %s")
            params.append(ativo)
        if password is not None:
            sets.append("password_hash = %s")
            params.append(hash_password(password))
        params.append(user_id)
        sql = f"UPDATE migracao.usuario SET {', '.join(sets)} WHERE id = %s::uuid"
        with psycopg.connect(self._conninfo) as conn:
            conn.execute(sql, params)
            conn.commit()
        u = self.get_by_id(user_id)
        if u is None:
            raise KeyError(user_id)
        return u

    def delete(self, user_id: str) -> None:
        with psycopg.connect(self._conninfo) as conn:
            conn.execute(
                "DELETE FROM migracao.usuario WHERE id = %s::uuid", (user_id,)
            )
            conn.commit()

    def touch_login(self, user_id: str) -> None:
        with psycopg.connect(self._conninfo, autocommit=True) as conn:
            conn.execute(
                "UPDATE migracao.usuario SET ultimo_login = now() WHERE id = %s::uuid",
                (user_id,),
            )

    def ensure_bootstrap_admin(self) -> None:
        """Se a tabela estiver vazia, cria admin a partir de ADMIN_USER/ADMIN_PASSWORD."""
        try:
            if self.count() > 0:
                return
        except Exception as exc:
            log.warning("Não foi possível contar usuários (tabela ausente?): %s", exc)
            return

        user = os.environ.get("ADMIN_USER", "admin").strip() or "admin"
        password = os.environ.get("ADMIN_PASSWORD", "").strip()
        if not password:
            log.warning(
                "Tabela de usuários vazia e ADMIN_PASSWORD não definida — "
                "nenhum admin foi criado automaticamente"
            )
            return
        try:
            self.create(user, password, Role.ADMIN.value, nome="Administrador")
            log.info("Admin bootstrap criado: username=%s role=admin", user)
        except Exception:
            log.exception("Falha ao criar admin bootstrap")
