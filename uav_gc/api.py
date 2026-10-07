import asyncio
import logging
import signal
import time
from contextlib import asynccontextmanager, suppress
from typing import Any

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

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    409: {"model": models.ErrorBody},
    422: {"model": models.ErrorBody},
    503: {"model": models.ErrorBody},
    504: {"model": models.ErrorBody},
}


async def _command_error_handler(request: Request, exc: errors.CommandError) -> JSONResponse:
    """Map a typed command failure to its HTTP response.

    Runs whenever the vehicle layer raises a `CommandError` out of a command
    endpoint -- before, during, or after the command reaches the vehicle:

    - pre-send: link down or mode map unknown (`NoLink`); unknown mode name
      (`UnknownMode`)
    - sending: the send failed (`NoLink`)
    - post-response: the vehicle refused (`Rejected`); no ack, or the mode did
      not change (`Timeout`)

    `code` selects the status and, with `message`, forms the `{code, message}`
    body:

    - `no_link` -> 503
    - `unknown_mode` -> 422
    - `rejected` -> 409
    - `timeout` -> 504

    Validation errors and other exceptions use their own handlers.
    """
    return JSONResponse(
        status_code=_STATUS[exc.code],
        content=models.ErrorBody(code=exc.code, message=exc.message).model_dump(),
    )


async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=models.ErrorBody(code=models.ErrorCode.invalid_request, message="invalid request").model_dump(),
    )


async def _internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    log.error("internal error", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=models.ErrorBody(code=models.ErrorCode.internal, message="internal error").model_dump(),
    )


def _supervisor_done(task: asyncio.Task) -> None:
    """Stop the server if `supervise()` dies: the link can never recover, and
    a server that stays up would only look healthy and never be restarted."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        log.error("supervisor died; shutting down", exc_info=exc)
        signal.raise_signal(signal.SIGINT)


def _make_lifespan(vehicle, supervise):
    @asynccontextmanager
    async def lifespan(app):
        task = None
        if supervise is not None:
            task = asyncio.create_task(supervise())
            task.add_done_callback(_supervisor_done)
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await task
            vehicle.link.close()

    return lifespan


def create_app(vehicle, supervise=None):
    app = FastAPI(lifespan=_make_lifespan(vehicle, supervise))

    # NOTE: Starlette types the handler's `exc` as the base `Exception`, so these
    # narrower handlers trip reportArgumentType (contravariant parameter).
    # See .venv/lib/python3.13/site-packages/starlette/types.py:24-26.
    app.add_exception_handler(errors.CommandError, _command_error_handler)  # pyright: ignore[reportArgumentType]
    app.add_exception_handler(RequestValidationError, _validation_error_handler)  # pyright: ignore[reportArgumentType]
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
