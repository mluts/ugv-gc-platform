import time

import jwt
import pytest
from argon2 import PasswordHasher
from argon2.profiles import CHEAPEST

from uav_gc.auth import ROLE_RANK, TokenCodec, hash_password, verify_password
from uav_gc.models import Role

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
