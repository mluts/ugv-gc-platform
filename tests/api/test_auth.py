import time

from tests.conftest import PASSWORDS
from uav_gc.auth import TokenCodec
from uav_gc.models import Role


def _login(client, username, password):
    return client.post("/auth/login", data={"username": username, "password": password})


def test_login_success(make_client):
    client, _ = make_client()
    client.headers.pop("Authorization", None)

    response = _login(client, Role.admin.value, PASSWORDS[Role.admin])

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"


def test_login_wrong_password_is_invalid_credentials(make_client):
    client, _ = make_client()
    client.headers.pop("Authorization", None)

    response = _login(client, Role.admin.value, "wrong")

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


def test_login_unknown_username_has_the_same_body(make_client):
    client, _ = make_client()
    client.headers.pop("Authorization", None)

    unknown = _login(client, "nobody", "whatever")
    wrong = _login(client, Role.admin.value, "wrong")

    assert unknown.status_code == 401
    assert unknown.json() == wrong.json()


def test_login_missing_fields_is_invalid_request(make_client):
    client, _ = make_client()
    client.headers.pop("Authorization", None)

    response = client.post("/auth/login", data={"username": "admin"})

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"


def test_me_returns_the_caller(make_client):
    client, tokens = make_client()
    client.headers["Authorization"] = f"Bearer {tokens[Role.operator]}"

    response = client.get("/auth/me")

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == Role.operator.value
    assert body["role"] == "operator"
    assert "id" in body


def test_me_without_token_is_unauthenticated(make_client):
    client, _ = make_client()
    client.headers.pop("Authorization", None)

    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json()["code"] == "unauthenticated"


def test_me_with_expired_token_is_unauthenticated(make_client):
    client, _ = make_client()
    expired = TokenCodec("test-secret", 1800, lambda: time.time() - 31 * 60)
    client.headers["Authorization"] = f"Bearer {expired.issue(1)}"

    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json()["code"] == "unauthenticated"


def test_me_with_forged_token_is_unauthenticated(make_client):
    client, _ = make_client()
    forged = TokenCodec("other-secret", 1800)
    client.headers["Authorization"] = f"Bearer {forged.issue(1)}"

    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json()["code"] == "unauthenticated"


def test_me_with_deleted_users_token_is_unauthenticated(make_client):
    client, tokens = make_client()
    client.headers["Authorization"] = f"Bearer {tokens[Role.operator]}"
    user_id = client.get("/auth/me").json()["id"]
    client.store.delete(user_id)

    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json()["code"] == "unauthenticated"
