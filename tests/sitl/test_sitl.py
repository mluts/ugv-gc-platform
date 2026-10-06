import pytest

pytestmark = pytest.mark.sitl

# ArduRover modes; a Copter-only mode such as "land" is rejected.
ROVER_MODES = {
    "MANUAL",
    "ACRO",
    "STEERING",
    "HOLD",
    "LOITER",
    "FOLLOW",
    "SIMPLE",
    "AUTO",
    "RTL",
    "SMART_RTL",
    "GUIDED",
    "INITIALISING",
}


def test_link_up_and_armable(client):
    state = client.get("/vehicle/state").json()
    assert state["link"]["status"] == "UP"
    assert state["armable"] is True


def test_state_reports_a_rover_mode(client):
    assert client.get("/vehicle/state").json()["mode"] in ROVER_MODES


def test_mode_change(client):
    # Rover: hop via HOLD so the change is a real one (as the old script did).
    assert client.post("/vehicle/mode", json={"mode": "hold"}).json() == {"mode": "HOLD"}
    assert client.post("/vehicle/mode", json={"mode": "manual"}).json() == {"mode": "MANUAL"}


def test_arm_and_disarm(client):
    assert client.post("/vehicle/arm").json() == {"armed": True}
    assert client.post("/vehicle/disarm").json() == {"armed": False}


def test_land_is_unknown_mode(client):
    response = client.post("/vehicle/mode", json={"mode": "land"})
    assert response.status_code == 422
    assert response.json()["code"] == "unknown_mode"
