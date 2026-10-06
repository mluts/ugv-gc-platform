import subprocess
import time

import pytest
from fastapi.testclient import TestClient

from uav_gc.api import create_app
from uav_gc.link import MavLink
from uav_gc.vehicle import Vehicle

# The simulator's TCP port serves one client at a time.
SIM_DEVICE = "tcp:127.0.0.1:5762"
READY_TIMEOUT_S = 180


@pytest.fixture(scope="session")
def client():
    # A no-op when the simulator is already running.
    subprocess.run(
        ["docker", "compose", "--profile", "sim", "up", "-d", "sitl"],
        check=True,
    )

    link = MavLink(SIM_DEVICE)
    vehicle = Vehicle(link)

    with TestClient(create_app(vehicle, link.supervise)) as client:
        deadline = time.monotonic() + READY_TIMEOUT_S
        while time.monotonic() < deadline:
            state = client.get("/vehicle/state").json()
            if state["link"]["status"] == "UP" and state["armable"]:
                break
            time.sleep(1)
        else:
            pytest.fail(
                f"simulator not UP and armable within {READY_TIMEOUT_S}s - "
                "is a bridge already connected to 127.0.0.1:5762?"
            )
        yield client
