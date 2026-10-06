import pytest

pytestmark = pytest.mark.sitl


def test_link_up_and_armable(client):
    state = client.get("/vehicle/state").json()
    assert state["link"]["status"] == "UP"
    assert state["armable"] is True
