from fastapi.testclient import TestClient

from tests.fakes import FakeVehicle
from uav_gc.api import create_app


def _schema():
    response = TestClient(create_app(FakeVehicle())).get("/openapi.json")
    assert response.status_code == 200
    return response.json()


def test_openapi_lists_four_paths():
    assert set(_schema()["paths"]) == {
        "/vehicle/state",
        "/vehicle/arm",
        "/vehicle/disarm",
        "/vehicle/mode",
    }


def test_link_status_is_enum():
    schemas = _schema()["components"]["schemas"]
    assert schemas["LinkStatus"]["enum"] == ["CONNECTING", "UP", "DOWN"]


def test_error_code_is_enum():
    schemas = _schema()["components"]["schemas"]
    assert schemas["ErrorCode"]["enum"] == [
        "rejected",
        "timeout",
        "no_link",
        "unknown_mode",
        "invalid_request",
        "internal",
    ]


def test_command_routes_declare_error_responses():
    schema = _schema()
    for path in ("/vehicle/arm", "/vehicle/disarm", "/vehicle/mode"):
        responses = schema["paths"][path]["post"]["responses"]
        assert {"409", "422", "503", "504"} <= set(responses)


def test_docs_returns_200():
    client = TestClient(create_app(FakeVehicle()))
    assert client.get("/docs").status_code == 200
