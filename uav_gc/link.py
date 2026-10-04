import asyncio

import re
import argparse
import time
from pymavlink import mavutil
from pymavlink.dialects.v20.ardupilotmega import MAVLink_message
from typing import Callable
import logging
from enum import auto, Enum
import socket

MAV = mavutil.mavlink

log = logging.getLogger(__name__)


class LinkDown(Exception):
    pass


class MavLink:
    HEARTBEAT_PERIOD = 1.0
    HEARTBEAT_TIMEOUT = 5.0

    conn: mavutil.mavfile

    class LinkStatus(Enum):
        CONNECTING = auto()
        UP = auto()
        DOWN = auto()

    def __init__(
        self,
        dev,
        baud=115200,
    ):
        self.dev = dev
        self.baud = baud

        self.latest: dict[str, tuple] = {}
        self.last_heartbeat_at: float | None = None
        self._hb_seen = asyncio.Event()

        self._once: list[tuple[Callable, asyncio.Future]] = []
        self._handlers: dict[int, list[Callable]] = {}
        self._started_at = None

        self.status = self.LinkStatus.DOWN
        self.last_error = None

        self._session_up_cbs: list[Callable] = []

        self._dead_reason = None

    @classmethod
    def from_args(cls):
        parser = argparse.ArgumentParser()
        transport = parser.add_mutually_exclusive_group(required=True)
        transport.add_argument(
            "--tcp",
            type=cls._host_port,
            action="store",
            help="TCP endpoint in the form host:port",
        )

        transport.add_argument(
            "--udp",
            type=cls._host_port,
            action="store",
            help="UDP endpoint in the form host:port",
        )

        transport.add_argument(
            "--serial",
            action="store",
            help="serial device path",
        )
        parser.add_argument(
            "--baud",
            type=int,
            default=None,
            help="serial baud rate (default: 115200)",
        )

        args = parser.parse_args()
        if args.serial:
            baud = args.baud if args.baud is not None else 115200
            if baud <= 0:
                parser.error("--baud must be a positive integer")
            return cls(args.serial, baud=baud)

        if args.baud is not None:
            parser.error("--baud can only be used with --serial")

        if args.tcp:
            return cls(f"tcp:{args.tcp}")

        return cls(f"udpin:{args.udp}")

    @staticmethod
    def _host_port(value):
        if not re.fullmatch(r"[^:]+:\d+", value):
            raise argparse.ArgumentTypeError("must be in the form host:port")

        return value

    def protocol_version(self):
        return self.conn.WIRE_PROTOCOL_VERSION

    def _start_reader(self):
        loop = asyncio.get_running_loop()
        loop.add_reader(self.conn.port.fileno(), self._on_readable)
        self._started_at = time.monotonic()

    async def up(self, timeout=10):
        async with asyncio.timeout(timeout):
            await self._hb_seen.wait()

        return self._hb_seen.is_set()

    def _mark_dead(self, reason: str):
        try:
            asyncio.get_running_loop().remove_reader(self.conn.port.fileno())
        except (OSError, ValueError):
            pass
        self._dead_reason = reason

    def _on_readable(self):
        # when you kill sitl, you get tcp doom loop on link :(
        if getattr(self.conn.port, "type", None) == socket.SOCK_STREAM:  # only for tcp
            try:
                if self.conn.port.recv(1, socket.MSG_PEEK) == b"":
                    self._mark_dead("EOF on link socket (peer closed)")
                    return
            except BlockingIOError:
                pass
            except OSError as e:
                self._mark_dead(f"socket error: {e}")
                return

        while (msg := self.conn.recv_match(blocking=False)) is not None:
            self._dispatch(msg)

    def _dispatch(self, msg: MAVLink_message):
        now = time.monotonic()
        self.latest[msg.get_type()] = (msg, now)

        if msg.get_msgId() == MAV.MAVLINK_MSG_ID_HEARTBEAT:
            self.last_heartbeat_at = now
            self._hb_seen.set()

        # Must run before _once, so consumers may use wait_for to wait for updated state
        if self._handlers:
            for cb in self._handlers.get(msg.get_msgId(), []):
                try:
                    cb(msg, now)
                except Exception:
                    log.exception("handler failed for %s", msg.get_type())

        if self._once:
            for pred, fut in self._once:
                try:
                    if not fut.done() and pred(msg):
                        fut.set_result(msg)
                except Exception:
                    log.exception("waiting_for handler failed for %s", msg.get_type())

            self._once = [(p, f) for p, f in self._once if not f.done()]

    # https://mavlink.io/en/messages/common.html#HEARTBEAT
    async def heartbeat_out(self):
        while True:
            self.conn.mav.heartbeat_send(
                MAV.MAV_TYPE_GCS, MAV.MAV_AUTOPILOT_INVALID, 0, 0, MAV.MAV_STATE_ACTIVE
            )
            await asyncio.sleep(self.HEARTBEAT_PERIOD)

    async def wait_for(self, pred, timeout=5.0):
        fut = asyncio.get_running_loop().create_future()
        self._once.append((pred, fut))

        try:
            async with asyncio.timeout(timeout):
                return await fut
        finally:
            if not fut.done():
                fut.cancel()

    def on(self, msg_id: int, cb: Callable) -> None:
        self._handlers.setdefault(msg_id, []).append(cb)

    async def _dial(self):
        self.conn = await asyncio.to_thread(
            mavutil.mavlink_connection, self.dev, baud=self.baud
        )

    def _teardown(self):
        if (conn := getattr(self, "conn", None)) is not None:
            try:
                asyncio.get_running_loop().remove_reader(conn.port.fileno())
            except (OSError, ValueError):
                pass
            conn.close()

        self.last_heartbeat_at = None
        self._hb_seen.clear()

        # Drop loudly wait_for listeners
        for _, fut in self._once:
            if not fut.done():
                fut.set_exception(LinkDown("link is down"))
        self._once.clear()
        self._dead_reason = None
        self._session_tg = None

    async def supervise(self):
        backoff = 1.0

        while True:
            self.status = self.LinkStatus.CONNECTING
            log.info("Connecting...")

            try:
                await self._dial()

                async with asyncio.TaskGroup() as tg:
                    self._start_reader()
                    self._session_tg: asyncio.TaskGroup | None = tg
                    tg.create_task(self.heartbeat_out())
                    tg.create_task(self.watchdog())

                    await self._hb_seen.wait()
                    log.info("Link is up...")
                    self.status = self.LinkStatus.UP
                    self.last_error = None
                    for cb in self._session_up_cbs:
                        tg.create_task(self._run_hook(cb))
                    backoff = 1.0

                    await asyncio.Event().wait()

            except* (LinkDown, ConnectionError, OSError) as eg:
                log.warning("Link is down...")
                self.status = self.LinkStatus.DOWN
                self.last_error = str(eg.exceptions[0])
                self._teardown()

            await asyncio.sleep(backoff)

            backoff = min(backoff * 2, 30.0)

    async def watchdog(self):
        while True:
            await asyncio.sleep(1)

            if self._started_at is None:
                raise RuntimeError("Can't start watchdog before link")

            if self._dead_reason:
                raise LinkDown(self._dead_reason)

            ref = self.last_heartbeat_at or self._started_at

            if (age := time.monotonic() - ref) > self.HEARTBEAT_TIMEOUT:
                raise LinkDown(f"No heartbeat for {age:.1f}s")

    def on_link_up(self, cb) -> None:
        self._session_up_cbs.append(cb)
        # late to the party, but still welcome
        if self.status == self.LinkStatus.UP and self._session_tg is not None:
            self._session_tg.create_task(self._run_hook(cb))

    async def _run_hook(self, cb):
        try:
            await cb()
        except LinkDown:
            pass
        except Exception:
            log.exception("session-up hook failed")
