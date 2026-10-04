from dataclasses import dataclass
from .link import MavLink
from . import command
from pymavlink import mavutil
import asyncio
import math

from pymavlink.dialects.v20.ardupilotmega import (
    MAVLink_heartbeat_message,
    MAVLink_heartbeat_message,
)

MAV = mavutil.mavlink
UINT16_MAX = (2**16) - 1
INT16_MAX = (2**15) - 1


def dist_m(lat1, lon1, lat2, lon2):
    k = 111_319.5  # m per degree latitude
    dx = (lon2 - lon1) * k * math.cos(math.radians(lat1))
    dy = (lat2 - lat1) * k
    return math.hypot(dx, dy)


@dataclass
class Position:
    lat: float
    lon: float  # deg
    alt_msl: float  # m
    alt_rel: float  # m
    vn: float
    ve: float
    vd: float  # m/s NED
    heading: float | None  # deg
    at: float


@dataclass
class Attitude:
    roll: float
    pitch: float
    yaw: float  # rad
    at: float


@dataclass
class Battery:
    id: int
    voltage: float | None  # V
    current: float | None  # A
    remaining_pct: int | None  # %
    temperature: int | None
    charge_state: str
    faults: int
    at: float


@dataclass
class EKF:
    flags: int
    at: float


@dataclass
class SysStatus:
    onboard_control_sensors_health: int
    at: float


class Vehicle:
    STREAM_RATES_US = {
        MAV.MAVLINK_MSG_ID_ATTITUDE: 250_000,  # 4Hz
        MAV.MAVLINK_MSG_ID_GLOBAL_POSITION_INT: 500_000,  # 2Hz
        MAV.MAVLINK_MSG_ID_SYS_STATUS: 1_000_000,  # 1Hz
        MAV.MAVLINK_MSG_ID_BATTERY_STATUS: 1_000_000,  # 1Hz
        MAV.MAVLINK_MSG_ID_EKF_STATUS_REPORT: 1_000_000,  # 1Hz
    }

    def __init__(self, link: MavLink):
        self.link = link
        self.position: Position | None = None
        self.attitude: Attitude | None = None
        self.batteries: dict[int, Battery] = {}
        self.last_heartbeat: tuple[MAVLink_heartbeat_message, float] | None = None

        self.link.on(MAV.MAVLINK_MSG_ID_GLOBAL_POSITION_INT, self._on_position)
        self.link.on(MAV.MAVLINK_MSG_ID_ATTITUDE, self._on_attitude)
        self.link.on(MAV.MAVLINK_MSG_ID_SYS_STATUS, self._on_sys_status)
        self.link.on(MAV.MAVLINK_MSG_ID_HEARTBEAT, self._on_heartbeat)
        self.link.on(MAV.MAVLINK_MSG_ID_BATTERY_STATUS, self._on_battery_status)
        self.link.on(MAV.MAVLINK_MSG_ID_EKF_STATUS_REPORT, self._on_ekf_status)
        self.link.on_link_up(self._on_up)

        self.mav_mode = None
        self.armed = None
        self.ekf = None

        self.sys_status = None

    async def get_message_interval(
        self, msg_id: int, timeout=3.0
    ) -> command.MessageIntervalMsg | None:

        cmd = command.ReqMessageInterval(msg_id, self.link)

        reply = asyncio.create_task(
            self.link.wait_for(
                lambda m: (
                    m.get_msgId() == MAV.MAVLINK_MSG_ID_MESSAGE_INTERVAL
                    and m.message_id == msg_id
                ),
                timeout=timeout,
            )
        )

        ack = asyncio.create_task(cmd.recv_ack(timeout))

        await asyncio.sleep(0)

        cmd.send()

        (done, _) = await asyncio.wait(
            {reply, ack}, return_when=asyncio.FIRST_COMPLETED
        )

        try:
            if ack in done and ack.result().is_unsuccessful():
                reply.cancel()
                return None

            return command.MessageIntervalMsg(await reply)
        except TimeoutError:
            return None
        finally:
            ack.cancel()
            reply.cancel()

    async def maybe_set_message_interval(self, msg_id):
        mi = await self.get_message_interval(msg_id)

        if mi is None or not mi.is_enabled():
            cmd = command.SetMessageInterval(
                msg_id, self.STREAM_RATES_US[msg_id], self.link
            )
            cmd.send()
            ack = await cmd.recv_ack(3.0)

            if ack.is_unsuccessful():
                if ack.is_no_response():
                    raise RuntimeError(
                        f"SET_MESSAGE_INTERVAL for MSG {msg_id} had no response: {ack.result()}"
                    )
                else:
                    raise RuntimeError(
                        f"SET_MESSAGE_INTERVAL for MSG {msg_id} refused: {ack.result()}"
                    )

    def _on_position(self, msg, at):
        self.position = Position(
            lat=msg.lat / 1e7,
            lon=msg.lon / 1e7,
            alt_msl=msg.alt / 1000,
            alt_rel=msg.relative_alt / 1000,
            vn=msg.vx / 100,
            ve=msg.vy / 100,
            vd=msg.vz / 100,
            heading=None if msg.hdg == UINT16_MAX else msg.hdg / 100,
            at=at,
        )

    def _on_attitude(self, msg, at):
        self.attitude = Attitude(roll=msg.roll, pitch=msg.pitch, yaw=msg.yaw, at=at)

    def _on_sys_status(self, msg, at):
        self.sys_status = SysStatus(msg.onboard_control_sensors_health, at)

    def _on_heartbeat(self, msg: MAVLink_heartbeat_message, at):
        if (
            msg.get_srcSystem() != self.link.conn.target_system
            or msg.autopilot == MAV.MAV_AUTOPILOT_INVALID
        ):
            return
        # self.mav_mode = MAV.enums["MAV_MODE"][msg.base_mode]
        self.mav_mode = mavutil.mode_string_v10(msg)
        self.armed = bool(msg.base_mode & MAV.MAV_MODE_FLAG_SAFETY_ARMED)
        self.last_heartbeat = (msg, at)

    async def _on_up(self):
        # can't parallelize, oterwise will mixup COMMAND_ACK
        await self.maybe_set_message_interval(MAV.MAVLINK_MSG_ID_SYS_STATUS)
        await self.maybe_set_message_interval(MAV.MAVLINK_MSG_ID_ATTITUDE)
        await self.maybe_set_message_interval(MAV.MAVLINK_MSG_ID_GLOBAL_POSITION_INT)
        await self.maybe_set_message_interval(MAV.MAVLINK_MSG_ID_BATTERY_STATUS)
        await self.maybe_set_message_interval(MAV.MAVLINK_MSG_ID_EKF_STATUS_REPORT)

    def _on_battery_status(self, msg, at):
        mv = sum(v for v in msg.voltages if v != UINT16_MAX)
        mv += sum(
            v for v in msg.voltages_ext if v != 0
        )  # NOTE: ext sentinel is 0, not UINT16_MAX

        self.batteries[msg.id] = Battery(
            id=msg.id,
            voltage=mv / 1000 if mv else None,
            current=None if msg.current_battery == -1 else msg.current_battery / 100,
            remaining_pct=None
            if msg.battery_remaining == -1
            else msg.battery_remaining,
            temperature=None if msg.temperature == INT16_MAX else msg.temperature / 100,
            charge_state=MAV.enums["MAV_BATTERY_CHARGE_STATE"][msg.charge_state].name,
            faults=msg.fault_bitmask,
            at=at,
        )

    def _on_ekf_status(self, msg, at):
        self.ekf = EKF(flags=msg.flags, at=at)

    @property
    def position_ok(self) -> bool:
        return bool(self.ekf and self.ekf.flags & MAV.EKF_POS_HORIZ_ABS)

    @property
    def armable(self) -> bool:
        return bool(
            self.ekf
            and self.ekf.flags & MAV.EKF_POS_HORIZ_ABS
            and self.sys_status
            and self.sys_status.onboard_control_sensors_health
            & MAV.MAV_SYS_STATUS_PREARM_CHECK
        )

    async def set_mode(self, name: str, timeout=5.0):
        mapping = self.link.conn.mode_mapping()

        if mapping is None:
            raise RuntimeError("mode map unknown (no heartbeat decoded yet)")

        if name not in mapping:
            raise ValueError(f"unknown mode {name}")

        cmd = command.CmdLong(
            self.link,
            MAV.MAV_CMD_DO_SET_MODE,
            MAV.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            mapping[name],
        )

        cmd.send()

        ack = await cmd.recv_ack(timeout)

        if not ack.is_accepted():
            raise RuntimeError(f"mode {name} refused: {ack.result()}")

        if self.mav_mode == name:
            return

        try:
            await self.link.wait_for(lambda _: self.mav_mode == name, timeout=timeout)
        except TimeoutError:
            raise RuntimeError(f"mode {name} accepted, but didn't actually change")

    async def _arm_disarm(self, want: bool, timeout=5.0):

        cmd = command.CmdLong(
            self.link, MAV.MAV_CMD_COMPONENT_ARM_DISARM, 1 if want else 0
        )

        cmd.send()

        ack = await cmd.recv_ack(timeout)

        if not ack.is_accepted():
            raise RuntimeError(
                f"{'arm' if want else 'disarm'} refused: {ack.result()[1].name}"
            )

        if self.armed == want:
            return
        try:
            await self.link.wait_for(lambda _: self.armed == want, timeout)
        except TimeoutError:
            raise RuntimeError(
                f"arm={want} accepted but not confirmed within {timeout}s"
            )

    async def arm(self, timeout=5.0):
        await self._arm_disarm(True, timeout)

    async def disarm(self, timeout=5.0):
        await self._arm_disarm(False, timeout)

    async def takeoff(self, alt_rel: float, timeout=45.0):
        if self.mav_mode != "GUIDED" or not self.armed:
            raise RuntimeError(
                f"takeoff requires GUIDED+armed (mode={self.mav_mode}, armed={self.armed})"
            )

        cmd = command.CmdLong(self.link, MAV.MAV_CMD_NAV_TAKEOFF, p7=alt_rel)
        cmd.send()

        ack = await cmd.recv_ack(3.0)

        if not ack.is_accepted():
            raise RuntimeError(f"takeoff refused: {ack.result()}")

        await self.link.wait_for(
            lambda _: self.position and self.position.alt_rel >= alt_rel * 0.95,
            timeout=timeout,
        )

    def _arrived(self, lat, lon, alt_rel, horizx_tol=2.0, alt_tol=2.0):
        p = self.position
        return (
            p
            and dist_m(p.lat, p.lon, lat, lon) < horizx_tol
            and abs(p.alt_rel - alt_rel) < alt_tol
        )

    # https://mavlink.io/en/messages/common.html#MAV_CMD_DO_REPOSITION
    # speed=-1 for default
    async def goto(
        self, lat: float, lon: float, alt_rel: int, speed=-1.0, timeout=None
    ):
        if self.mav_mode != "GUIDED":
            raise RuntimeError(f"goto requires GUIDED (mode={self.mav_mode})")

        cmd = command.CmdInt(
            self.link,
            MAV.MAV_CMD_DO_REPOSITION,
            p1=speed,
            p2=0,
            p4=float("nan"),
            x=int(round(lat * 1e7)),
            y=int(round(lon * 1e7)),
            z=alt_rel,
            frame=MAV.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
        )
        cmd.send()

        ack = await cmd.recv_ack(3.0)

        if not ack.is_accepted():
            raise RuntimeError(f"reposition refused: {ack.result()}")

        if self.position is None:
            raise RuntimeError(f"can't navigate without position:")

        if timeout is None:
            timeout = 10 + dist_m(self.position.lat, self.position.lon, lat, lon) / 2

        await self.link.wait_for(lambda _: self._arrived(lat, lon, alt_rel), timeout)
