import asyncio
import logging
import signal
import time
from contextlib import asynccontextmanager, suppress
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm

from . import errors, models
from .auth import hash_password, verify_password

log = logging.getLogger(__name__)

_STATUS = {
    "unauthenticated": 401,
    "forbidden": 403,
    "invalid_credentials": 401,
    "not_found": 404,
    "username_taken": 409,
    "last_admin": 409,
    "rejected": 409,
    "timeout": 504,
    "no_link": 503,
    "unknown_mode": 422,
}

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": models.ErrorBody},
    403: {"model": models.ErrorBody},
    409: {"model": models.ErrorBody},
    422: {"model": models.ErrorBody},
    503: {"model": models.ErrorBody},
    504: {"model": models.ErrorBody},
}


async def _api_error_handler(request: Request, exc: errors.ApiError) -> JSONResponse:
    """Map a typed API failure to its HTTP response.

    ``code`` selects the status and, with ``message``, forms the
    ``{code, message}`` body; the two 401 codes carry ``WWW-Authenticate:
    Bearer``. Validation errors and other exceptions use their own handlers.
    """
    status = _STATUS[exc.code]
    return JSONResponse(
        status_code=status,
        content=models.ErrorBody(code=exc.code, message=exc.message).model_dump(),
        headers={"WWW-Authenticate": "Bearer"} if status == 401 else None,
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


def _make_lifespan(vehicle, supervise, users):
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
            users.close()

    return lifespan


def create_app(vehicle, supervise=None, *, users, auth):
    app = FastAPI(lifespan=_make_lifespan(vehicle, supervise, users), redoc_url=None)

    # NOTE: Starlette types the handler's `exc` as the base `Exception`, so these
    # narrower handlers trip reportArgumentType (contravariant parameter).
    # See .venv/lib/python3.13/site-packages/starlette/types.py:24-26.
    app.add_exception_handler(errors.ApiError, _api_error_handler)  # pyright: ignore[reportArgumentType]
    app.add_exception_handler(RequestValidationError, _validation_error_handler)  # pyright: ignore[reportArgumentType]
    app.add_exception_handler(Exception, _internal_error_handler)

    @app.get("/vehicle/state", responses=_ERROR_RESPONSES, dependencies=[Depends(auth.require(models.Role.viewer))])
    def state() -> models.VehicleState:
        return vehicle.state(time.monotonic())

    @app.post("/vehicle/arm", responses=_ERROR_RESPONSES, dependencies=[Depends(auth.require(models.Role.operator))])
    async def arm() -> models.ArmedResponse:
        await vehicle.arm()
        return models.ArmedResponse(armed=vehicle.armed)

    @app.post("/vehicle/disarm", responses=_ERROR_RESPONSES, dependencies=[Depends(auth.require(models.Role.operator))])
    async def disarm() -> models.ArmedResponse:
        await vehicle.disarm()
        return models.ArmedResponse(armed=vehicle.armed)

    @app.post("/vehicle/mode", responses=_ERROR_RESPONSES, dependencies=[Depends(auth.require(models.Role.operator))])
    async def set_mode(body: models.ModeRequest) -> models.ModeResponse:
        await vehicle.set_mode(body.mode.upper())
        return models.ModeResponse(mode=vehicle.mav_mode)

    @app.post("/auth/login")
    def login(form: Annotated[OAuth2PasswordRequestForm, Depends()]) -> models.Token:
        stored = auth.users.get_by_username(form.username)
        password_hash = stored.password_hash if stored is not None else None
        ok = verify_password(auth.hasher, password_hash, form.password)
        if not ok or stored is None:
            raise errors.InvalidCredentials("invalid credentials")
        return models.Token(access_token=auth.codec.issue(stored.id))

    @app.get("/auth/me", responses=_ERROR_RESPONSES)
    def me(user: Annotated[models.User, Depends(auth.require(models.Role.viewer))]) -> models.User:
        return user

    @app.get("/users", responses=_ERROR_RESPONSES, dependencies=[Depends(auth.require(models.Role.admin))])
    def list_users() -> list[models.User]:
        return auth.users.list()

    @app.post("/users", status_code=201, responses=_ERROR_RESPONSES, dependencies=[Depends(auth.require(models.Role.admin))])
    def create_user(body: models.UserCreate) -> models.User:
        password_hash = hash_password(auth.hasher, body.password)
        return auth.users.create(body.username, password_hash, body.role)

    @app.patch("/users/{id}", responses=_ERROR_RESPONSES, dependencies=[Depends(auth.require(models.Role.admin))])
    def update_user(id: int, body: models.UserUpdate) -> models.User:
        password_hash = hash_password(auth.hasher, body.password) if body.password is not None else None
        return auth.users.update(id, password_hash=password_hash, role=body.role)

    @app.delete("/users/{id}", status_code=204, responses=_ERROR_RESPONSES, dependencies=[Depends(auth.require(models.Role.admin))])
    def delete_user(id: int) -> None:
        auth.users.delete(id)

    return app
