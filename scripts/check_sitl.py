#!/usr/bin/env python3

import sys

from uav_gc import link, command, vehicle
import asyncio
from functools import reduce
import logging
import os

MAV = link.MAV

log = logging.getLogger(__name__)

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)

#
def every_pred(*preds):
    return lambda v: reduce((lambda res, pred: res and pred(v)), preds, True)


IsSysStatusMsg = lambda msg: msg.get_msgId() == MAV.MAVLINK_MSG_ID_SYS_STATUS
SysStatusPrearmReady = lambda msg: (
    msg.onboard_control_sensors_health & MAV.MAV_SYS_STATUS_PREARM_CHECK
)


class Check:
    indent = ""

    def __indent(self):
        print(self.indent, end="")

    def log(self, *msg):
        self.__indent()
        print(*msg)

    def step(self, name, ok, detail=""):
        status = "PASS" if ok else "FAIL"

        self.__indent()
        print(f"[{status}] {name}" + (f" - {detail if detail else ''}"))

        if not ok:
            sys.exit(1)

        self.indent += " " * 2


async def main():
    check = Check()

    c = link.MavLink.from_args()

    supervise = asyncio.get_running_loop().create_task(c.supervise())

    check.log("checking heartbeat...")

    is_up = await c.up()

    check.step("hearbeat", is_up, f"sysid={c.conn.target_system}")

    check.log("checking prearm readiness...")

    cmd = command.ReqSysStatus(c)
    cmd.send()
    msg = await c.wait_for(
        every_pred(IsSysStatusMsg, SysStatusPrearmReady),
        30
    )

    check.step("prearm check", msg, f"sysid={c.conn.target_system}")

    uav = vehicle.Vehicle(c)

    print(f"uav mode {uav.mav_mode}")
    print(f"uav armed {uav.armed}")

    await c.wait_for(lambda _: uav.armable, timeout=90)

    await uav.set_mode("GUIDED")
    await uav.arm()

    await c.wait_for(lambda _: uav.armed)

    print(f"uav mode {uav.mav_mode}")
    print(f"uav armed {uav.armed}")

    supervise.cancel()


if __name__ == "__main__":
    asyncio.run(main())
