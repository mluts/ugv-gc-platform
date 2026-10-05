from fastapi.testclient import TestClient

from tests.fakes import FakeVehicle
from uav_gc import errors
from uav_gc.api import create_app


def _client(vehicle=None):
    return TestClient(create_app(vehicle or FakeVehicle()))


def test_rejected():
    vehicle = FakeVehicle()
    vehicle.arm_error = errors.Rejected("arm refused: MAV_RESULT_FAILED")
    response = _client(vehicle).post("/vehicle/arm")

    assert response.status_code == 409
    assert response.json() == {
        "code": "rejected",
        "message": "arm refused: MAV_RESULT_FAILED",
    }


def test_timeout():
    vehicle = FakeVehicle()
    vehicle.arm_error = errors.Timeout("arm: no acknowledgement")
    response = _client(vehicle).post("/vehicle/arm")

    assert response.status_code == 504
    assert response.json()["code"] == "timeout"


def test_no_link():
    vehicle = FakeVehicle()
    vehicle.arm_error = errors.NoLink("link is not up")
    response = _client(vehicle).post("/vehicle/arm")

    assert response.status_code == 503
    assert response.json()["code"] == "no_link"


def test_unknown_mode():
    vehicle = FakeVehicle()
    vehicle.set_mode_error = errors.UnknownMode("unknown mode LAND")
    response = _client(vehicle).post("/vehicle/mode", json={"mode": "LAND"})

    assert response.status_code == 422
    assert response.json()["code"] == "unknown_mode"


def test_invalid_request():
    response = _client().post("/vehicle/mode")  # no body

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"


def test_internal():
    vehicle = FakeVehicle()
    vehicle.arm_error = RuntimeError("boom")
    client = TestClient(create_app(vehicle), raise_server_exceptions=False)
    response = client.post("/vehicle/arm")

    assert response.status_code == 500
    assert response.json() == {"code": "internal", "message": "internal error"}
    assert "Traceback" not in response.text
