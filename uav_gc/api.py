import logging
import time

from fastapi import FastAPI

from . import models

log = logging.getLogger(__name__)


def create_app(vehicle, supervise=None):
    app = FastAPI()

    @app.get("/vehicle/state")
    def state() -> models.VehicleState:
        return vehicle.state(time.monotonic())

    @app.post("/vehicle/arm")
    async def arm() -> models.ArmedResponse:
        await vehicle.arm()
        return models.ArmedResponse(armed=vehicle.armed)

    @app.post("/vehicle/disarm")
    async def disarm() -> models.ArmedResponse:
        await vehicle.disarm()
        return models.ArmedResponse(armed=vehicle.armed)

    @app.post("/vehicle/mode")
    async def set_mode(body: models.ModeRequest) -> models.ModeResponse:
        await vehicle.set_mode(body.mode.upper())
        return models.ModeResponse(mode=vehicle.mav_mode)

    return app
