from types import SimpleNamespace

import pytest
from pymavlink import mavutil

from uav_gc import errors
from uav_gc.link import LinkDown, MavLink
from uav_gc.vehicle import Vehicle

MAV = mavutil.mavlink

_UNSET = object()


class FakeAck:
    """A COMMAND_ACK message that only exposes the fields `CommandAckMsg` reads."""

    def __init__(self, result):
        self.result = result


class ScriptedLink:
    """A link fake whose `wait_for` consumes a queue of scripted outcomes."""

    def __init__(self, *, status=MavLink.LinkStatus.UP, mode_map=_UNSET):
        self.status = status
        self.mode_map = {} if mode_map is _UNSET else mode_map
        self.sent = []
        self.send_error = None
        self.script = []  # outcomes for `wait_for` calls, consumed in order
        self.conn = SimpleNamespace(
            target_system=1,
            target_component=1,
            mode_mapping=self._mode_mapping,
            mav=SimpleNamespace(command_long_send=self._send),
        )

    def _mode_mapping(self):
        return self.mode_map

    def _send(self, *args, **kwargs):
        self.sent.append(args)
        if self.send_error:
            raise self.send_error

    def on(self, msg_id, cb):
        pass

    def on_link_up(self, cb):
        pass

    async def wait_for(self, pred, timeout=5.0):
        if not self.script:
            raise AssertionError("scripted wait_for called with no outcome queued")
        kind, *rest = self.script.pop(0)
        if kind == "ack":
            (result,) = rest
            return FakeAck(result)
        if kind == "timeout":
            raise TimeoutError
        if kind == "linkdown":
            raise LinkDown("link is down")
        raise AssertionError(f"unknown scripted outcome: {kind}")


# --- pre-send checks -------------------------------------------------------


async def test_no_link_when_link_down():
    link = ScriptedLink(status=MavLink.LinkStatus.DOWN)
    vehicle = Vehicle(link)

    with pytest.raises(errors.NoLink):
        await vehicle.set_mode("HOLD")
    with pytest.raises(errors.NoLink):
        await vehicle.arm()

    assert link.sent == []


async def test_no_link_when_mode_map_unknown():
    link = ScriptedLink(mode_map=None)
    vehicle = Vehicle(link)

    with pytest.raises(errors.NoLink) as exc:
        await vehicle.set_mode("HOLD")

    assert "mode map unknown" in str(exc.value)
    assert link.sent == []


async def test_unknown_mode():
    link = ScriptedLink(mode_map={"HOLD": 4})
    vehicle = Vehicle(link)

    with pytest.raises(errors.UnknownMode) as exc:
        await vehicle.set_mode("LAND")

    assert "LAND" in str(exc.value)
    assert link.sent == []


# --- acknowledgement outcomes ----------------------------------------------


async def test_timeout_when_no_ack():
    link = ScriptedLink(mode_map={"HOLD": 4})
    link.script.append(("timeout",))
    vehicle = Vehicle(link)

    with pytest.raises(errors.Timeout):
        await vehicle.set_mode("HOLD")


async def test_rejected():
    link = ScriptedLink(mode_map={"HOLD": 4})
    link.script.append(("ack", MAV.MAV_RESULT_FAILED))
    vehicle = Vehicle(link)

    with pytest.raises(errors.Rejected) as exc:
        await vehicle.set_mode("HOLD")

    assert "MAV_RESULT_FAILED" in str(exc.value)


# --- confirmation outcomes -------------------------------------------------


async def test_timeout_when_not_confirmed():
    link = ScriptedLink(mode_map={"HOLD": 4})
    link.script.append(("ack", MAV.MAV_RESULT_ACCEPTED))
    link.script.append(("timeout",))
    vehicle = Vehicle(link)

    with pytest.raises(errors.Timeout):
        await vehicle.set_mode("HOLD")


# --- link loss -------------------------------------------------------------


async def test_no_link_on_linkdown_while_waiting_for_ack():
    link = ScriptedLink(mode_map={"HOLD": 4})
    link.script.append(("linkdown",))
    vehicle = Vehicle(link)

    with pytest.raises(errors.NoLink):
        await vehicle.set_mode("HOLD")


async def test_no_link_on_linkdown_while_waiting_for_confirmation():
    link = ScriptedLink(mode_map={"HOLD": 4})
    link.script.append(("ack", MAV.MAV_RESULT_ACCEPTED))
    link.script.append(("linkdown",))
    vehicle = Vehicle(link)

    with pytest.raises(errors.NoLink):
        await vehicle.set_mode("HOLD")


async def test_no_link_on_send_error():
    link = ScriptedLink(mode_map={"HOLD": 4})
    link.send_error = OSError("broken pipe")
    vehicle = Vehicle(link)

    with pytest.raises(errors.NoLink):
        await vehicle.set_mode("HOLD")


# --- success paths ---------------------------------------------------------


async def test_set_mode_success():
    link = ScriptedLink(mode_map={"HOLD": 4})
    link.script.append(("ack", MAV.MAV_RESULT_ACCEPTED))
    vehicle = Vehicle(link)
    vehicle.mav_mode = "HOLD"

    await vehicle.set_mode("HOLD")

    assert len(link.sent) == 1


async def test_arm_success():
    link = ScriptedLink()
    link.script.append(("ack", MAV.MAV_RESULT_ACCEPTED))
    vehicle = Vehicle(link)
    vehicle.armed = True

    await vehicle.arm()

    assert len(link.sent) == 1


async def test_disarm_success():
    link = ScriptedLink()
    link.script.append(("ack", MAV.MAV_RESULT_ACCEPTED))
    vehicle = Vehicle(link)
    vehicle.armed = False

    await vehicle.disarm()

    assert len(link.sent) == 1
