"""Authentication: password hashing, tokens, and the API's auth dependency.

Passwords are argon2id hashes; the hasher is an argument, never a module
global, so the fast test suite can use a cheap profile. Tokens are JWT HS256
whose subject is the user id; the clock is injected so tests can mint an
expired token without sleeping. `Auth.require(role)` is the FastAPI dependency
that reads the bearer token and enforces the role.
"""

import time
from collections.abc import Callable
from typing import Annotated

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from .errors import Forbidden, NotFound, Unauthenticated
from .models import Role, User
from .users import UserStore

# NOTE: A fixed argon2id hash (production parameters) verified when the
# username is unknown, so a login for a missing user costs the same as one with
# a wrong password. Its plaintext is irrelevant; only the full verify matters.
DUMMY_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$B3jGL+iV/YFO1r7kH071mw"
    "$W1iPYbNTKRU2cJ1I1khMqlFsZnZNJzLhQGIz22Z4bh0"
)

# Each role includes the rights of the one before it.
ROLE_RANK: dict[Role, int] = {
    Role.viewer: 0,
    Role.operator: 1,
    Role.admin: 2,
}

# Reads the `Authorization: Bearer <token>` header. `auto_error=False` lets a
# missing header fall through to `Auth.authenticate`, so the 401 body is ours.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def hash_password(hasher: PasswordHasher, password: str) -> str:
    return hasher.hash(password)


def verify_password(hasher: PasswordHasher, password_hash: str | None, password: str) -> bool:
    """Check ``password`` against ``password_hash``.

    ``None`` means the user is unknown: a fixed dummy hash is verified instead
    so the timing matches a wrong password, and the result is always ``False``.
    """
    if password_hash is None:
        try:
            hasher.verify(DUMMY_HASH, password)
        except VerificationError:
            pass
        return False

    try:
        return hasher.verify(password_hash, password)
    except VerificationError:
        return False


class TokenCodec:
    """Issues and decodes HS256 tokens carrying the user id as ``sub``."""

    def __init__(self, secret: str, ttl_s: int, now: Callable[[], float] = time.time):
        self.secret = secret
        self.ttl_s = ttl_s
        self.now = now

    def issue(self, user_id: int) -> str:
        issued = int(self.now())
        return jwt.encode(
            {"sub": str(user_id), "iat": issued, "exp": issued + self.ttl_s},
            self.secret,
            algorithm="HS256",
        )

    def decode(self, token: str) -> int:
        """Return the user id, or raise ``jwt.InvalidTokenError``.

        Expiry is checked against the real clock; the injected ``now`` is only
        used when issuing.
        """
        claims = jwt.decode(token, self.secret, algorithms=["HS256"])
        return int(claims["sub"])


class Auth:
    """Authentication and authorization for the API.

    Holds the store, codec and hasher; `require(role)` is the FastAPI
    dependency the routes use.
    """

    def __init__(self, users: UserStore, codec: TokenCodec, hasher: PasswordHasher):
        self.users = users
        self.codec = codec
        self.hasher = hasher

    def authenticate(self, token: str | None) -> User:
        """Return the user the token belongs to, or raise `Unauthenticated`."""
        if not token:
            raise Unauthenticated("not authenticated")
        try:
            user_id = self.codec.decode(token)
        except jwt.InvalidTokenError as exc:
            raise Unauthenticated("invalid token") from exc
        try:
            return self.users.get(user_id)
        except NotFound as exc:
            raise Unauthenticated("user no longer exists") from exc

    def authorize(self, user: User, role: Role) -> None:
        """Raise `Forbidden` if the user's role is below `role`."""
        if ROLE_RANK[user.role] < ROLE_RANK[role]:
            raise Forbidden("forbidden")

    def require(self, role: Role):
        """A FastAPI dependency that authenticates the caller and enforces `role`."""

        def check(token: Annotated[str | None, Depends(oauth2_scheme)]) -> User:
            user = self.authenticate(token)
            self.authorize(user, role)
            return user

        return check
