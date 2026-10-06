from uav_gc import models


class FakeLink:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeVehicle:
    """A fake exposing the four methods `create_app` depends on."""

    def __init__(self, state=None):
        self._state = state if state is not None else self._empty_state()
        self.link = FakeLink()
        self.armed = self._state.armed
        self.mav_mode = self._state.mode
        self.calls = []
        self.arm_error = None
        self.disarm_error = None
        self.set_mode_error = None

    @staticmethod
    def _empty_state():
        return models.VehicleState(
            position=None,
            attitude=None,
            batteries=[],
            mode=None,
            armed=None,
            armable=False,
            armable_age_s=None,
            position_ok=False,
            link=models.Link(
                status=models.LinkStatus.DOWN,
                last_error=None,
                heartbeat_age_s=None,
            ),
            ts=0.0,
            protocol_version=None,
        )

    def state(self, now):
        return self._state

    async def arm(self):
        self.calls.append("arm")
        if self.arm_error is not None:
            raise self.arm_error
        self.armed = True

    async def disarm(self):
        self.calls.append("disarm")
        if self.disarm_error is not None:
            raise self.disarm_error
        self.armed = False

    async def set_mode(self, name):
        self.calls.append(("set_mode", name))
        if self.set_mode_error is not None:
            raise self.set_mode_error
        self.mav_mode = name
