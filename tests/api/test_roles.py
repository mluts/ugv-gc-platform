import pytest

from tests.fakes import FakeVehicle
from uav_gc.models import Role


def _auth_header(tokens, role):
    return {"Authorization": f"Bearer {tokens[role]}"}


def test_state_without_token_is_unauthenticated(make_client):
    client, _ = make_client()
    client.headers.pop("Authorization", None)

    response = client.get("/vehicle/state")

    assert response.status_code == 401
    assert response.json()["code"] == "unauthenticated"
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_state_with_viewer_token_is_ok(make_client):
    client, tokens = make_client()
    client.headers.update(_auth_header(tokens, Role.viewer))

    assert client.get("/vehicle/state").status_code == 200


@pytest.mark.parametrize("path", ["/vehicle/arm", "/vehicle/disarm"])
def test_command_without_token_is_unauthenticated(make_client, path):
    vehicle = FakeVehicle()
    client, _ = make_client(vehicle)
    client.headers.pop("Authorization", None)

    response = client.post(path)

    assert response.status_code == 401
    assert response.json()["code"] == "unauthenticated"
    assert vehicle.calls == []


def test_mode_without_token_is_unauthenticated(make_client):
    client, _ = make_client()
    client.headers.pop("Authorization", None)

    response = client.post("/vehicle/mode", json={"mode": "HOLD"})

    assert response.status_code == 401
    assert response.json()["code"] == "unauthenticated"


def test_command_with_viewer_token_is_forbidden_and_does_not_reach_vehicle(make_client):
    vehicle = FakeVehicle()
    client, tokens = make_client(vehicle)
    client.headers.update(_auth_header(tokens, Role.viewer))

    response = client.post("/vehicle/arm")

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"
    assert vehicle.calls == []


@pytest.mark.parametrize("role", [Role.operator, Role.admin])
def test_commands_with_operator_and_admin_tokens_are_allowed(make_client, role):
    vehicle = FakeVehicle()
    client, tokens = make_client(vehicle)
    client.headers.update(_auth_header(tokens, role))

    assert client.post("/vehicle/arm").status_code == 200
    assert client.post("/vehicle/disarm").status_code == 200
    assert client.post("/vehicle/mode", json={"mode": "HOLD"}).status_code == 200


def test_me_without_token_is_unauthenticated(make_client):
    client, _ = make_client()
    client.headers.pop("Authorization", None)

    assert client.get("/auth/me").status_code == 401


def test_me_with_viewer_token_is_ok(make_client):
    client, tokens = make_client()
    client.headers.update(_auth_header(tokens, Role.viewer))

    assert client.get("/auth/me").status_code == 200


def test_users_without_token_is_unauthenticated(make_client):
    client, _ = make_client()
    client.headers.pop("Authorization", None)

    assert client.get("/users").status_code == 401


@pytest.mark.parametrize("role", [Role.viewer, Role.operator])
def test_users_below_admin_is_forbidden(make_client, role):
    client, tokens = make_client()
    client.headers.update(_auth_header(tokens, role))

    response = client.get("/users")

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


def test_users_with_admin_is_ok(make_client):
    client, tokens = make_client()
    client.headers.update(_auth_header(tokens, Role.admin))

    assert client.get("/users").status_code == 200


def test_user_mutations_below_admin_are_forbidden(make_client):
    client, tokens = make_client()
    client.headers.update(_auth_header(tokens, Role.operator))

    assert client.post("/users", json={"username": "x", "password": "y", "role": "viewer"}).status_code == 403
    assert client.patch("/users/1", json={"role": "viewer"}).status_code == 403
    assert client.delete("/users/1").status_code == 403
