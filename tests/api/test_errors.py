from tests.fakes import FakeVehicle
from uav_gc import errors


def test_rejected(make_client):
    vehicle = FakeVehicle()
    vehicle.arm_error = errors.Rejected("arm refused: MAV_RESULT_FAILED")
    client, _ = make_client(vehicle)
    response = client.post("/vehicle/arm")

    assert response.status_code == 409
    assert response.json() == {
        "code": "rejected",
        "message": "arm refused: MAV_RESULT_FAILED",
    }


def test_timeout(make_client):
    vehicle = FakeVehicle()
    vehicle.arm_error = errors.Timeout("arm: no acknowledgement")
    client, _ = make_client(vehicle)
    response = client.post("/vehicle/arm")

    assert response.status_code == 504
    assert response.json()["code"] == "timeout"


def test_no_link(make_client):
    vehicle = FakeVehicle()
    vehicle.arm_error = errors.NoLink("link is not up")
    client, _ = make_client(vehicle)
    response = client.post("/vehicle/arm")

    assert response.status_code == 503
    assert response.json()["code"] == "no_link"


def test_unknown_mode(make_client):
    vehicle = FakeVehicle()
    vehicle.set_mode_error = errors.UnknownMode("unknown mode LAND")
    client, _ = make_client(vehicle)
    response = client.post("/vehicle/mode", json={"mode": "LAND"})

    assert response.status_code == 422
    assert response.json()["code"] == "unknown_mode"


def test_invalid_request(make_client):
    client, _ = make_client()
    response = client.post("/vehicle/mode")  # no body

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"


def test_internal(make_client):
    vehicle = FakeVehicle()
    vehicle.arm_error = RuntimeError("boom")
    client, _ = make_client(vehicle, raise_server_exceptions=False)
    response = client.post("/vehicle/arm")

    assert response.status_code == 500
    assert response.json() == {"code": "internal", "message": "internal error"}
    assert "Traceback" not in response.text
