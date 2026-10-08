def _schema(make_client):
    client, _ = make_client()
    response = client.get("/openapi.json")
    assert response.status_code == 200
    return response.json()


def test_openapi_lists_every_path(make_client):
    assert set(_schema(make_client)["paths"]) == {
        "/vehicle/state",
        "/vehicle/arm",
        "/vehicle/disarm",
        "/vehicle/mode",
        "/auth/login",
        "/auth/me",
        "/users",
        "/users/{id}",
    }


def test_link_status_is_enum(make_client):
    schemas = _schema(make_client)["components"]["schemas"]
    assert schemas["LinkStatus"]["enum"] == ["CONNECTING", "UP", "DOWN"]


def test_error_code_is_enum(make_client):
    schemas = _schema(make_client)["components"]["schemas"]
    assert schemas["ErrorCode"]["enum"] == [
        "rejected",
        "timeout",
        "no_link",
        "unknown_mode",
        "unauthenticated",
        "forbidden",
        "invalid_credentials",
        "not_found",
        "username_taken",
        "last_admin",
        "invalid_request",
        "internal",
    ]


def test_command_routes_declare_error_responses(make_client):
    schema = _schema(make_client)
    for path in ("/vehicle/arm", "/vehicle/disarm", "/vehicle/mode"):
        responses = schema["paths"][path]["post"]["responses"]
        assert {"401", "403", "409", "422", "503", "504"} <= set(responses)


def test_security_scheme_is_oauth2_password(make_client):
    schema = _schema(make_client)

    oauth2 = [s for s in schema["components"]["securitySchemes"].values() if s["type"] == "oauth2"]
    assert len(oauth2) == 1
    assert oauth2[0]["flows"]["password"]["tokenUrl"] == "/auth/login"

    assert schema["paths"]["/vehicle/state"]["get"]["security"]
    assert "security" not in schema["paths"]["/auth/login"]["post"]


def test_docs_returns_200(make_client):
    client, _ = make_client()
    assert client.get("/docs").status_code == 200


def test_redoc_is_not_served(make_client):
    client, _ = make_client()
    assert client.get("/redoc").status_code == 404
