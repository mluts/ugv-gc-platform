import time

import jwt
import pytest
from argon2 import PasswordHasher
from argon2.profiles import CHEAPEST

from uav_gc.auth import ROLE_RANK, Auth, TokenCodec, hash_password, verify_password
from uav_gc.errors import Forbidden, Unauthenticated
from uav_gc.models import Role
from uav_gc.users import UserStore

HASHER = PasswordHasher.from_parameters(CHEAPEST)


def test_password_round_trip():
    hashed = hash_password(HASHER, "s3cret")

    assert hashed != "s3cret"
    assert verify_password(HASHER, hashed, "s3cret") is True


def test_wrong_password_fails():
    hashed = hash_password(HASHER, "s3cret")

    assert verify_password(HASHER, hashed, "wrong") is False


def test_unknown_user_verifies_against_dummy_and_fails():
    assert verify_password(HASHER, None, "s3cret") is False


def test_token_round_trip():
    codec = TokenCodec("secret", 1800, time.time)

    assert codec.decode(codec.issue(7)) == 7


def test_expired_token_is_rejected():
    issued_at = time.time() - 31 * 60
    codec = TokenCodec("secret", 1800, lambda: issued_at)

    with pytest.raises(jwt.ExpiredSignatureError):
        codec.decode(codec.issue(7))


def test_token_signed_with_another_secret_is_rejected():
    issuer = TokenCodec("secret-a", 1800, time.time)
    verifier = TokenCodec("secret-b", 1800, time.time)

    with pytest.raises(jwt.InvalidTokenError):
        verifier.decode(issuer.issue(7))


def test_tampered_token_is_rejected():
    codec = TokenCodec("secret", 1800, time.time)
    token = codec.issue(7)
    middle = len(token) // 2
    tampered = token[:middle] + ("a" if token[middle] != "a" else "b") + token[middle + 1 :]

    with pytest.raises(jwt.InvalidTokenError):
        codec.decode(tampered)


def test_role_rank_orders_roles():
    assert ROLE_RANK[Role.admin] > ROLE_RANK[Role.operator] > ROLE_RANK[Role.viewer]


@pytest.fixture
def auth_ctx():
    store = UserStore(":memory:")
    hasher = PasswordHasher.from_parameters(CHEAPEST)
    codec = TokenCodec("secret", 1800)
    user = store.create("alice", hash_password(hasher, "pw"), Role.viewer)
    yield Auth(store, codec, hasher), store, codec, user
    store.close()


def test_authenticate_returns_the_user(auth_ctx):
    auth, _, codec, user = auth_ctx

    assert auth.authenticate(codec.issue(user.id)) == user


def test_authenticate_rejects_a_bad_token(auth_ctx):
    auth, _, _, _ = auth_ctx

    with pytest.raises(Unauthenticated):
        auth.authenticate("not-a-token")


def test_authenticate_rejects_a_missing_token(auth_ctx):
    auth, _, _, _ = auth_ctx

    with pytest.raises(Unauthenticated):
        auth.authenticate(None)


def test_authenticate_rejects_an_expired_token(auth_ctx):
    auth, _, _, user = auth_ctx
    expired = TokenCodec("secret", 1800, lambda: time.time() - 31 * 60)

    with pytest.raises(Unauthenticated):
        auth.authenticate(expired.issue(user.id))


def test_authenticate_rejects_a_deleted_users_token(auth_ctx):
    auth, store, codec, user = auth_ctx
    token = codec.issue(user.id)
    store.delete(user.id)

    with pytest.raises(Unauthenticated):
        auth.authenticate(token)


def test_authorize_rejects_a_lower_role(auth_ctx):
    auth, _, _, user = auth_ctx

    with pytest.raises(Forbidden):
        auth.authorize(user, Role.operator)


def test_authorize_allows_an_equal_or_higher_role(auth_ctx):
    auth, _, _, user = auth_ctx

    auth.authorize(user, Role.viewer)
