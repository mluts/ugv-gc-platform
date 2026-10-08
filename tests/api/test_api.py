from tests.fakes import FakeVehicle
from uav_gc import models


def test_state_shape(make_client):
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
            armable_age_s=0.2,
            position_ok=False,
            link=models.Link(
                status=models.LinkStatus.UP, last_error=None, heartbeat_age_s=1.0
            ),
            ts=123.0,
            protocol_version="2.0",
        )
    )
    client, _ = make_client(vehicle)
    response = client.get("/vehicle/state")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "position",
        "attitude",
        "batteries",
        "mode",
        "armed",
        "armable",
        "armable_age_s",
        "position_ok",
        "link",
        "ts",
        "protocol_version",
    }
    assert body["mode"] == "HOLD"
    assert body["link"]["status"] == "UP"
    assert body["protocol_version"] == "2.0"


def test_arm_success(make_client):
    client, _ = make_client()
    response = client.post("/vehicle/arm")

    assert response.status_code == 200
    assert response.json() == {"armed": True}


def test_disarm_success(make_client):
    vehicle = FakeVehicle()
    vehicle.armed = True
    client, _ = make_client(vehicle)
    response = client.post("/vehicle/disarm")

    assert response.status_code == 200
    assert response.json() == {"armed": False}


def test_mode_success(make_client):
    client, _ = make_client()
    response = client.post("/vehicle/mode", json={"mode": "HOLD"})

    assert response.status_code == 200
    assert response.json() == {"mode": "HOLD"}


def test_mode_case_insensitive(make_client):
    vehicle = FakeVehicle()
    client, _ = make_client(vehicle)
    response = client.post("/vehicle/mode", json={"mode": "hold"})

    assert response.status_code == 200
    assert response.json() == {"mode": "HOLD"}
    assert ("set_mode", "HOLD") in vehicle.calls


def test_old_paths_return_404(make_client):
    client, _ = make_client()

    assert client.get("/stats").status_code == 404
    assert client.post("/arm").status_code == 404
    assert client.post("/disarm").status_code == 404
    assert client.post("/mode").status_code == 404
