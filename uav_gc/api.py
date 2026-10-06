import logging
import time

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import errors, models

log = logging.getLogger(__name__)

_STATUS = {
    "rejected": 409,
    "timeout": 504,
    "no_link": 503,
    "unknown_mode": 422,
}

_ERROR_RESPONSES = {
    409: {"model": models.ErrorBody},
    422: {"model": models.ErrorBody},
    503: {"model": models.ErrorBody},
    504: {"model": models.ErrorBody},
}


async def _command_error_handler(request: Request, exc: errors.CommandError) -> JSONResponse:
    return JSONResponse(
        status_code=_STATUS[exc.code],
        content=models.ErrorBody(code=exc.code, message=exc.message).model_dump(),
    )


async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=models.ErrorBody(code="invalid_request", message="invalid request").model_dump(),
    )


async def _internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    log.error("internal error", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=models.ErrorBody(code="internal", message="internal error").model_dump(),
    )


def create_app(vehicle, supervise=None):
    app = FastAPI()

    app.add_exception_handler(errors.CommandError, _command_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(Exception, _internal_error_handler)

    @app.get("/vehicle/state")
    def state() -> models.VehicleState:
        return vehicle.state(time.monotonic())

    @app.post("/vehicle/arm", responses=_ERROR_RESPONSES)
    async def arm() -> models.ArmedResponse:
        await vehicle.arm()
        return models.ArmedResponse(armed=vehicle.armed)

    @app.post("/vehicle/disarm", responses=_ERROR_RESPONSES)
    async def disarm() -> models.ArmedResponse:
        await vehicle.disarm()
        return models.ArmedResponse(armed=vehicle.armed)

    @app.post("/vehicle/mode", responses=_ERROR_RESPONSES)
    async def set_mode(body: models.ModeRequest) -> models.ModeResponse:
        await vehicle.set_mode(body.mode.upper())
        return models.ModeResponse(mode=vehicle.mav_mode)

    return app
