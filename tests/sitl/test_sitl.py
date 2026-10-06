import subprocess
import time

import pytest

pytestmark = pytest.mark.sitl

# How stale the data behind `armable` may be to still count as a fresh reading.
FRESH_S = 2.0

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


def _compose(*args):
    subprocess.run(["docker", "compose", "--profile", "sim", *args], check=True)


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


# NOTE: last on purpose - it restarts the simulator and is the slowest test.
def test_link_loss_and_recovery(client):
    _compose("kill", "sitl")

    # The link notices the dead socket, then goes DOWN.
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if client.get("/vehicle/state").json()["link"]["status"] != "UP":
            break
        time.sleep(0.5)
    else:
        pytest.fail("link still UP 10s after killing the simulator")

    # A command now fails fast instead of waiting for a timeout.
    start = time.monotonic()
    response = client.post("/vehicle/arm")
    assert time.monotonic() - start < 1.0
    assert response.status_code == 503
    assert response.json()["code"] == "no_link"

    # Restart; the supervisor reconnects on its own.
    _compose("up", "-d", "sitl")

    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        state = client.get("/vehicle/state").json()
        fresh = state["armable_age_s"] is not None and state["armable_age_s"] < FRESH_S
        if state["link"]["status"] == "UP" and state["armable"] and fresh:
            break
        time.sleep(1)
    else:
        pytest.fail("simulator did not come back UP and armable")
