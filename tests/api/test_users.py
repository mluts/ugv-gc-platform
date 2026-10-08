from uav_gc.models import Role


def _create(client, username, password, role):
    return client.post(
        "/users", json={"username": username, "password": password, "role": role.value}
    )


def _find_user(client, username):
    return next(u for u in client.get("/users").json() if u["username"] == username)


def test_create_then_log_in(make_client):
    client, _ = make_client()

    response = _create(client, "bob", "bob-password", Role.operator)

    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "bob"
    assert body["role"] == "operator"
    login = client.post("/auth/login", data={"username": "bob", "password": "bob-password"})
    assert login.status_code == 200


def test_listing_hides_secrets(make_client):
    client, _ = make_client()

    response = client.get("/users")

    assert response.status_code == 200
    assert all(set(entry) == {"id", "username", "role"} for entry in response.json())


def test_duplicate_username_is_username_taken(make_client):
    client, _ = make_client()

    response = _create(client, Role.admin.value, "x", Role.viewer)

    assert response.status_code == 409
    assert response.json()["code"] == "username_taken"


def test_unknown_user_is_not_found(make_client):
    client, _ = make_client()

    response = client.patch("/users/9999", json={"role": "viewer"})

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    assert client.delete("/users/9999").status_code == 404


def test_password_change(make_client):
    client, _ = make_client()
    user_id = _create(client, "bob", "old", Role.viewer).json()["id"]

    response = client.patch(f"/users/{user_id}", json={"password": "new"})

    assert response.status_code == 200
    assert client.post("/auth/login", data={"username": "bob", "password": "old"}).status_code == 401
    assert client.post("/auth/login", data={"username": "bob", "password": "new"}).status_code == 200


def test_invalid_role_is_invalid_request(make_client):
    client, _ = make_client()

    response = client.post("/users", json={"username": "bob", "password": "x", "role": "pilot"})

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"


def test_deleting_the_only_admin_is_last_admin(make_client):
    client, _ = make_client()
    admin_id = _find_user(client, Role.admin.value)["id"]

    response = client.delete(f"/users/{admin_id}")

    assert response.status_code == 409
    assert response.json()["code"] == "last_admin"


def test_demoting_the_only_admin_is_last_admin(make_client):
    client, _ = make_client()
    admin_id = _find_user(client, Role.admin.value)["id"]

    response = client.patch(f"/users/{admin_id}", json={"role": "operator"})

    assert response.status_code == 409
    assert response.json()["code"] == "last_admin"


def test_deleting_one_of_two_admins(make_client):
    client, _ = make_client()
    _create(client, "second-admin", "pw", Role.admin)
    admin_id = _find_user(client, Role.admin.value)["id"]

    assert client.delete(f"/users/{admin_id}").status_code == 204


def test_demotion_takes_effect_on_the_next_request(make_client):
    client, tokens = make_client()
    client.headers["Authorization"] = f"Bearer {tokens[Role.operator]}"
    assert client.post("/vehicle/arm").status_code == 200

    client.headers["Authorization"] = f"Bearer {tokens[Role.admin]}"
    operator_id = _find_user(client, Role.operator.value)["id"]
    assert client.patch(f"/users/{operator_id}", json={"role": "viewer"}).status_code == 200

    client.headers["Authorization"] = f"Bearer {tokens[Role.operator]}"
    assert client.post("/vehicle/arm").status_code == 403
