import asyncio
import dataclasses
import time
import logging

from aiohttp import web

from .link import MavLink
from .vehicle import Vehicle

log = logging.getLogger(__name__)


def snapshot(vehicle: Vehicle, link: MavLink) -> dict:
    now = time.monotonic()

    hb = vehicle.last_heartbeat

    def group(dc):
        if dc is None:
            return None

        d = dataclasses.asdict(dc)

        d["age_s"] = round(now - d.pop("at"), 2)

        return d

    return {
        "position": group(vehicle.position),
        "attitude": group(vehicle.attitude),
        "batteries": [group(b) for b in vehicle.batteries.values()],
        "mode": vehicle.mav_mode,
        "armed": vehicle.armed,
        "armable": vehicle.armable,
        "position_ok": vehicle.position_ok,
        "link": {
            "status": link.status.name,
            "last_error": link.last_error,
            "heartbeat_age_s": None if hb is None else round(now - hb[1], 2),
        },
        "ts": time.time(),
        "protocol_version": link.protocol_version()
    }


async def do_arm(vehicle: Vehicle) -> dict:
    try:
        await vehicle.arm()

        return {"armed": vehicle.armed}
    except (RuntimeError, ValueError, TimeoutError) as e:
        return {"armed": vehicle.armed, "error": str(e)}


async def do_disarm(vehicle: Vehicle) -> dict:
    try:
        await vehicle.disarm()

        return {"armed": vehicle.armed}
    except (RuntimeError, ValueError, TimeoutError) as e:
        return {"armed": vehicle.armed, "error": str(e)}


async def do_set_mode(vehicle: Vehicle, mode: str) -> dict:
    try:
        await vehicle.set_mode(mode and mode.upper())
        return {"mode": vehicle.mav_mode}
    except (RuntimeError, ValueError, TimeoutError) as e:
        return {"mode": vehicle.mav_mode, "error": str(e)}


class Api:
    def __init__(self, vehicle: Vehicle, link: MavLink):
        self.vehicle = vehicle
        self.link = link

    async def stats(self, _: web.Request) -> web.Response:
        return web.json_response(snapshot(self.vehicle, self.link))

    async def arm(self, _: web.Request) -> web.Response:
        resp = await do_arm(self.vehicle)
        return web.json_response(resp, status=400 if "error" in resp else 200)

    async def disarm(self, _: web.Request) -> web.Response:
        resp = await do_disarm(self.vehicle)
        return web.json_response(resp, status=400 if "error" in resp else 200)

    async def set_mode(self, req: web.Request) -> web.Response:
        newmode = req.query.get("newmode")
        if newmode is None:
            return web.json_response(
                {"error": 'please specify "newmode" param'}, status=400
            )

        resp = await do_set_mode(self.vehicle, newmode)
        return web.json_response(resp, status=400 if "error" in resp else 200)

    def app(self) -> web.Application:
        app = web.Application()
        app.router.add_get("/stats", self.stats)
        app.router.add_post("/arm", self.arm)
        app.router.add_post("/disarm", self.disarm)
        app.router.add_post("/mode", self.set_mode)
        return app

    async def serve(self, host="127.0.0.1", port=8080):
        runner = web.AppRunner(self.app())

        await runner.setup()
        await web.TCPSite(runner, host, port).start()

        log.info(f"HTTP Server started on: {host}:{port}")

        try:
            await asyncio.Event().wait()
        finally:
            await runner.cleanup()
