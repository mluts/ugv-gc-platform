"""SQLite user store.

One table holds users and their argon2 password hashes. The store only stores
hashes -- it never computes them -- and every method takes a lock because the
FastAPI threadpool and the test client call it from several threads.
"""

import sqlite3
import threading
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path

from .errors import LastAdmin, NotFound, UsernameTaken
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
    """CRUD over the ``users`` table, serialised behind a lock.

    Ownership: this store owns its ``sqlite3.Connection``.

    It opens the connection in ``__init__`` (``check_same_thread=False``),
    keeps it in a closure so there is no reachable ``self._conn`` attribute,
    holds the lock around every use so statements cannot interleave,
    and closes it in `close()`.

    Callers receive plain ``User`` objects, never the connection.

    The lock is per instance, not per file: two stores pointed at the same
    path hold two independent locks, and safety between them is SQLite's,
    not this class's.
    """

    def __init__(self, path: str | Path):
        path = str(path)
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        lock = threading.Lock()

        @contextmanager
        def locked() -> Iterator[sqlite3.Connection]:
            """Yield the connection with the lock held -- the only way to touch it."""
            with lock:
                yield conn

        self._locked: Callable[[], AbstractContextManager[sqlite3.Connection]] = locked
        with self._locked() as c:
            c.execute(_SCHEMA)
            c.commit()

    def close(self) -> None:
        with self._locked() as conn:
            conn.close()

    def count(self) -> int:
        with self._locked() as conn:
            return self._count(conn)

    def _count(self, conn: sqlite3.Connection) -> int:
        row = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()
        return int(row["n"])

    def _admin_count(self, conn: sqlite3.Connection) -> int:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM users WHERE role = ?", (Role.admin.value,)
        ).fetchone()
        return int(row["n"])

    def list(self) -> list[User]:
        with self._locked() as conn:
            rows = conn.execute(
                "SELECT id, username, role FROM users ORDER BY id"
            ).fetchall()
        return [
            User(id=row["id"], username=row["username"], role=Role(row["role"]))
            for row in rows
        ]

    def get(self, user_id: int) -> User:
        with self._locked() as conn:
            row = conn.execute(
                "SELECT id, username, role FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        if row is None:
            raise NotFound(f"user {user_id} not found")
        return User(id=row["id"], username=row["username"], role=Role(row["role"]))

    def get_by_username(self, username: str) -> StoredUser | None:
        with self._locked() as conn:
            row = conn.execute(
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
        with self._locked() as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                    (username, password_hash, role.value),
                )
                conn.commit()
            except sqlite3.IntegrityError as exc:
                raise UsernameTaken(f"username {username} is taken") from exc
            user_id = cursor.lastrowid
        assert user_id is not None
        return User(id=user_id, username=username, role=role)

    def _check_before_removing_admin(self, conn):
        """Raise if there's only 1 admin left"""
        if self._admin_count(conn) <= 1:
            raise LastAdmin(f"can't remove last admin")

    def update(
        self,
        user_id: int,
        password_hash: str | None = None,
        role: Role | None = None,
    ) -> User:
        with self._locked() as conn:
            row = conn.execute(
                "SELECT id, username, role FROM users WHERE id = ?", (user_id,)
            ).fetchone()

            if row is None:
                raise NotFound(f"user {user_id} not found")

            # Maybe update role
            if role is not None:
                current_role = Role(row["role"])
                if current_role == Role.admin and role != Role.admin:
                    self._check_before_removing_admin(conn)
                conn.execute(
                    "UPDATE users SET role = ? WHERE id = ?", (role.value, user_id)
                )

            # Maybe update password
            if password_hash is not None:
                conn.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (password_hash, user_id),
                )

            conn.commit()
            username = row["username"]

        return User(id=user_id, username=username, role=role or row["role"])

    def delete(self, user_id: int) -> None:
        with self._locked() as conn:
            row = conn.execute(
                "SELECT role FROM users WHERE id = ?", (user_id,)
            ).fetchone()

            if row is None:
                raise NotFound(f"user {user_id} not found")

            if Role(row["role"]) == Role.admin:
                self._check_before_removing_admin(conn)

            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()

    def bootstrap(self, username: str, password_hash: str) -> User | None:
        """Create the first admin, but only while the store is empty."""
        with self._locked() as conn:
            if self._count(conn) > 0:
                return None
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (username, password_hash, Role.admin.value),
            )
            conn.commit()
            user_id = cursor.lastrowid

        assert user_id is not None

        return User(id=user_id, username=username, role=Role.admin)
