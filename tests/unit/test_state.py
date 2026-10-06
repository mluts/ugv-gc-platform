from uav_gc.link import MavLink
from uav_gc.models import LinkStatus, VehicleState
from uav_gc.vehicle import Attitude, Battery, Position, Vehicle


def _vehicle():
    return Vehicle(MavLink("tcp:127.0.0.1:1"))


def test_empty_state():
    state = _vehicle().state(now=0.0)

    assert isinstance(state, VehicleState)
    assert state.position is None
    assert state.attitude is None
    assert state.batteries == []
    assert state.mode is None
    assert state.armed is None
    assert state.armable is False
    assert state.armable_age_s is None
    assert state.position_ok is False
    assert state.link.status == LinkStatus.DOWN
    assert state.link.last_error is None
    assert state.link.heartbeat_age_s is None
    assert state.protocol_version is None


def test_ages_computed_from_given_time():
    vehicle = _vehicle()
    vehicle.position = Position(1.0, 2.0, 3.0, 4.0, 0.0, 0.0, 0.0, None, at=100.0)
    vehicle.attitude = Attitude(0.1, 0.2, 0.3, at=101.0)
    vehicle.batteries[0] = Battery(
        0, 12.6, 0.0, 100, None, "MAV_BATTERY_CHARGE_STATE_OK", 0, at=102.0
    )

    state = vehicle.state(now=105.0)

    assert state.position.lat == 1.0
    assert state.position.heading is None
    assert state.position.age_s == 5.0
    assert state.attitude.age_s == 4.0
    assert state.batteries[0].age_s == 3.0
    assert state.batteries[0].voltage == 12.6
