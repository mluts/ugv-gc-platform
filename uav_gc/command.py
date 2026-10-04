from dataclasses import dataclass
from .link import MavLink
from typing import Any
from pymavlink import mavutil
from functools import partial

MAV = mavutil.mavlink


@dataclass(frozen=True)
class AckMissing:
    name: str

    def description(self):
        return self.name


@dataclass(frozen=True)
class CommandAckMsg:
    msg: Any

    def result(self):
        if self.msg:
            return self.msg.result, MAV.enums["MAV_RESULT"][self.msg.result]
        else:
            return None, AckMissing("No response for COMMAND_ACK")

    def is_in_progress(self) -> bool:
        return self.result()[0] == MAV.MAV_RESULT_IN_PROGRESS

    def is_accepted(self) -> bool:
        return self.result()[0] == MAV.MAV_RESULT_ACCEPTED

    def is_unsuccessful(self) -> bool:
        return not (self.is_in_progress() or self.is_accepted())

    def is_no_response(self) -> bool:
        return not self.msg


@dataclass(frozen=True)
class MessageIntervalMsg:
    msg: Any

    def is_enabled(self):
        return self.msg.interval_us > 0


@dataclass(frozen=True)
class CmdLong:
    client: MavLink
    cmd_id: int
    p1: float = 0
    p2: float = 0
    p3: float = 0
    p4: float = 0
    p5: float = 0
    p6: float = 0
    p7: float = 0

    def send(self, confirmation: int = 0):
        # print("Sending")
        c = self.client.conn

        c.mav.command_long_send(
            c.target_system,
            c.target_component,
            self.cmd_id,
            confirmation,
            self.p1,
            self.p2,
            self.p3,
            self.p4,
            self.p5,
            self.p6,
            self.p7,
        )

    async def recv_ack(self, timeout) -> CommandAckMsg:
        try:
            return CommandAckMsg(
                await self.client.wait_for(
                    lambda m: (
                        m.get_msgId() == MAV.MAVLINK_MSG_ID_COMMAND_ACK
                        and m.command == self.cmd_id
                    ),
                    timeout,
                )
            )
        except TimeoutError:
            return CommandAckMsg(None)


@dataclass(frozen=True)
class CmdInt:
    client: MavLink
    cmd_id: int
    p1: float = 0
    p2: float = 0
    p3: float = 0
    p4: float = 0
    x: int = 0
    y: int = 0
    z: int = 0
    frame: int = 0

    def send(self):
        # print("Sending")
        c = self.client.conn

        c.mav.command_int_send(
            c.target_system,
            c.target_component,
            self.frame,
            self.cmd_id,
            0,  # deprecated: current
            0,  # deprecated: autocontinue
            self.p1,
            self.p2,
            self.p3,
            self.p4,
            self.x,
            self.y,
            self.z,
        )

    async def recv_ack(self, timeout) -> CommandAckMsg:
        try:
            return CommandAckMsg(
                await self.client.wait_for(
                    lambda m: (
                        m.get_msgId() == MAV.MAVLINK_MSG_ID_COMMAND_ACK
                        and m.command == self.cmd_id
                    ),
                    timeout,
                )
            )
        except TimeoutError:
            return CommandAckMsg(None)


ReqMessage = lambda msg_id, client: CmdLong(
    client, cmd_id=MAV.MAV_CMD_REQUEST_MESSAGE, p1=msg_id
)

ReqSysStatus = partial(ReqMessage, MAV.MAVLINK_MSG_ID_SYS_STATUS)

# ReqMessageInterval(msg_id, client) - request interval for given msg_id
ReqMessageInterval = lambda msg_id, client: CmdLong(
    client,
    cmd_id=MAV.MAV_CMD_REQUEST_MESSAGE,
    p1=MAV.MAVLINK_MSG_ID_MESSAGE_INTERVAL,
    p2=msg_id,
)

SetMessageInterval = lambda msg_id, interval_us, client: CmdLong(
    client, MAV.MAV_CMD_SET_MESSAGE_INTERVAL, msg_id, interval_us
)
