from fastapi.testclient import TestClient

from tests.fakes import FakeVehicle
from uav_gc import models
from uav_gc.api import create_app


def _client(vehicle=None):
    return TestClient(create_app(vehicle or FakeVehicle()))


def test_state_shape():
    vehicle = FakeVehicle(
        state=models.VehicleState(
            position=models.Position(
                lat=0.0,
                lon=0.0,
                alt_msl=0.0,
                alt_rel=0.0,
                vn=0.0,
                ve=0.0,
                vd=0.0,
                heading=None,
                age_s=0.0,
            ),
            attitude=None,
            batteries=[],
            mode="HOLD",
            armed=False,
            armable=False,
            position_ok=False,
            link=models.Link(
                status=models.LinkStatus.UP, last_error=None, heartbeat_age_s=1.0
            ),
            ts=123.0,
            protocol_version="2.0",
        )
    )
    response = _client(vehicle).get("/vehicle/state")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "position",
        "attitude",
        "batteries",
        "mode",
        "armed",
        "armable",
        "position_ok",
        "link",
        "ts",
        "protocol_version",
    }
    assert body["mode"] == "HOLD"
    assert body["link"]["status"] == "UP"
    assert body["protocol_version"] == "2.0"


def test_arm_success():
    response = _client().post("/vehicle/arm")

    assert response.status_code == 200
    assert response.json() == {"armed": True}


def test_disarm_success():
    vehicle = FakeVehicle()
    vehicle.armed = True
    response = _client(vehicle).post("/vehicle/disarm")

    assert response.status_code == 200
    assert response.json() == {"armed": False}


def test_mode_success():
    response = _client().post("/vehicle/mode", json={"mode": "HOLD"})

    assert response.status_code == 200
    assert response.json() == {"mode": "HOLD"}


def test_mode_case_insensitive():
    vehicle = FakeVehicle()
    response = _client(vehicle).post("/vehicle/mode", json={"mode": "hold"})

    assert response.status_code == 200
    assert response.json() == {"mode": "HOLD"}
    assert ("set_mode", "HOLD") in vehicle.calls


def test_old_paths_return_404():
    client = _client()

    assert client.get("/stats").status_code == 404
    assert client.post("/arm").status_code == 404
    assert client.post("/disarm").status_code == 404
    assert client.post("/mode").status_code == 404
