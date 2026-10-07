"""Pydantic models for the HTTP state document.

These mirror the internal dataclasses in `vehicle.py`, minus the monotonic `at`
timestamp, plus the derived `age_s`. The `Vehicle.state(now)` method builds them,
replacing the old `api.snapshot` dict assembly.
"""

from enum import Enum

from pydantic import BaseModel


class LinkStatus(str, Enum):
    CONNECTING = "CONNECTING"
    UP = "UP"
    DOWN = "DOWN"


class Position(BaseModel):
    lat: float
    lon: float
    alt_msl: float
    alt_rel: float
    vn: float
    ve: float
    vd: float
    heading: float | None
    age_s: float


class Attitude(BaseModel):
    roll: float
    pitch: float
    yaw: float
    age_s: float


class Battery(BaseModel):
    id: int
    voltage: float | None
    current: float | None
    remaining_pct: int | None
    temperature: float | None
    charge_state: str
    faults: int
    age_s: float


class Link(BaseModel):
    status: LinkStatus
    last_error: str | None
    heartbeat_age_s: float | None


class VehicleState(BaseModel):
    position: Position | None
    attitude: Attitude | None
    batteries: list[Battery]
    mode: str | None
    armed: bool | None
    armable: bool
    armable_age_s: float | None
    position_ok: bool
    link: Link
    ts: float
    protocol_version: str | None


class ModeRequest(BaseModel):
    mode: str


class ArmedResponse(BaseModel):
    armed: bool


class ModeResponse(BaseModel):
    mode: str


class Role(str, Enum):
    viewer = "viewer"
    operator = "operator"
    admin = "admin"


class User(BaseModel):
    id: int
    username: str
    role: Role


class UserCreate(BaseModel):
    username: str
    password: str
    role: Role


class UserUpdate(BaseModel):
    password: str | None = None
    role: Role | None = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ErrorCode(str, Enum):
    rejected            = "rejected"
    timeout             = "timeout"
    no_link             = "no_link"
    unknown_mode        = "unknown_mode"
    unauthenticated     = "unauthenticated"
    forbidden           = "forbidden"
    invalid_credentials = "invalid_credentials"
    not_found           = "not_found"
    username_taken      = "username_taken"
    last_admin          = "last_admin"
    invalid_request     = "invalid_request"
    internal            = "internal"


class ErrorBody(BaseModel):
    code: ErrorCode
    message: str
