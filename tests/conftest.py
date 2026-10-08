import pytest
from argon2 import PasswordHasher
from argon2.profiles import CHEAPEST
from fastapi.testclient import TestClient

from tests.fakes import FakeVehicle
from uav_gc import auth
from uav_gc.api import create_app
from uav_gc.models import Role
from uav_gc.users import UserStore

PASSWORDS = {
    Role.viewer: "viewer-password",
    Role.operator: "operator-password",
    Role.admin: "admin-password",
}


@pytest.fixture
def make_client():
    """Factory: build an app over an in-memory store with one user per role."""

    def factory(vehicle=None, supervise=None, **client_kwargs):
        store = UserStore(":memory:")
        hasher = PasswordHasher.from_parameters(CHEAPEST)
        codec = auth.TokenCodec("test-secret", 1800)
        users = {
            role: store.create(role.value, auth.hash_password(hasher, password), role)
            for role, password in PASSWORDS.items()
        }
        app = create_app(
            vehicle or FakeVehicle(), supervise, users=store, auth=auth.Auth(store, codec, hasher)
        )
        client = TestClient(app, **client_kwargs)
        client.store = store
        tokens = {role: codec.issue(user.id) for role, user in users.items()}
        # Authenticated as admin by default; role tests override or clear it.
        client.headers["Authorization"] = f"Bearer {tokens[Role.admin]}"
        return client, tokens

    return factory
