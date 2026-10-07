"""SQLite user store.

One table holds users and their argon2 password hashes. The store only stores
hashes -- it never computes them -- and every method takes a lock because the
FastAPI threadpool and the test client call it from several threads.
"""

import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

from .errors import NotFound, UsernameTaken
from .models import Role, User

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS users ("
    "id INTEGER PRIMARY KEY, "
    "username TEXT UNIQUE NOT NULL, "
    "password_hash TEXT NOT NULL, "
    "role TEXT NOT NULL)"
)


@dataclass(frozen=True)
class StoredUser:
    """A user row including the password hash, for the login path only."""

    id: int
    username: str
    password_hash: str
    role: Role

    def to_user(self) -> User:
        return User(id=self.id, username=self.username, role=self.role)


class UserStore:
    """CRUD over the ``users`` table, serialised behind a lock."""

    def __init__(self, path: str | Path):
        path = str(path)
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute(_SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def count(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()
        return int(row["n"])

    def list(self) -> list[User]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, username, role FROM users ORDER BY id"
            ).fetchall()
        return [
            User(id=row["id"], username=row["username"], role=Role(row["role"]))
            for row in rows
        ]

    def get(self, user_id: int) -> User:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, username, role FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        if row is None:
            raise NotFound(f"user {user_id} not found")
        return User(id=row["id"], username=row["username"], role=Role(row["role"]))

    def get_by_username(self, username: str) -> StoredUser | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, username, password_hash, role FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        if row is None:
            return None
        return StoredUser(
            id=row["id"],
            username=row["username"],
            password_hash=row["password_hash"],
            role=Role(row["role"]),
        )

    def create(self, username: str, password_hash: str, role: Role) -> User:
        with self._lock:
            try:
                cursor = self._conn.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                    (username, password_hash, role.value),
                )
                self._conn.commit()
            except sqlite3.IntegrityError as exc:
                raise UsernameTaken(f"username {username} is taken") from exc
            user_id = cursor.lastrowid
        assert user_id is not None
        return User(id=user_id, username=username, role=role)

    def update(
        self,
        user_id: int,
        password_hash: str | None = None,
        role: Role | None = None,
    ) -> User:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, username, role FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if row is None:
                raise NotFound(f"user {user_id} not found")
            if password_hash is not None:
                self._conn.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (password_hash, user_id),
                )
            if role is not None:
                self._conn.execute(
                    "UPDATE users SET role = ? WHERE id = ?", (role.value, user_id)
                )
            self._conn.commit()
            username = row["username"]
            current_role = role if role is not None else Role(row["role"])
        return User(id=user_id, username=username, role=current_role)

    def delete(self, user_id: int) -> None:
        with self._lock:
            cursor = self._conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            self._conn.commit()
            deleted = cursor.rowcount
        if deleted == 0:
            raise NotFound(f"user {user_id} not found")
