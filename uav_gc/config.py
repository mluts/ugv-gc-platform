"""Validated configuration for the bridge.

One TOML file, parsed with the standard library's ``tomllib`` and validated by
Pydantic, so an unknown key, a wrong type or a missing required key stops the
bridge with a message naming the key. Relative paths resolve against the
directory of the file, not the working directory.
"""

import logging
import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

log = logging.getLogger(__name__)

# NOTE: Development placeholder shipped in config.example.toml. The bridge logs
# a warning while this exact value is in use; the example file repeats the value
# so the check and the file cannot drift.
EXAMPLE_SECRET = "change-me-in-production-0123456789abcdef"


class ConfigError(Exception):
    """The configuration file is missing, unreadable or invalid."""


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HttpConfig(_Section):
    host: str = "127.0.0.1"
    port: int = 8080


class LinkConfig(_Section):
    device: str
    baud: int = 115200


class LogConfig(_Section):
    level: str = "INFO"


class AuthConfig(_Section):
    secret: str = Field(min_length=1)
    token_ttl_min: int = 30


class UsersConfig(_Section):
    database: str = "data/users.db"
    admin_username: str | None = None
    admin_password: str | None = None


class Config(_Section):
    http: HttpConfig = Field(default_factory=HttpConfig)
    link: LinkConfig
    log: LogConfig = Field(default_factory=LogConfig)
    auth: AuthConfig
    users: UsersConfig = Field(default_factory=UsersConfig)


def load_config(path: str | Path = "config.toml") -> Config:
    """Read, validate and normalise the configuration file.

    Raises ``ConfigError`` naming the path when it cannot be read, or naming
    the offending key when a value fails validation.
    """
    path = Path(path)

    try:
        with path.open("rb") as fh:
            raw = tomllib.load(fh)
    except FileNotFoundError as exc:
        raise ConfigError(f"configuration file not found: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in {path}: {exc}") from exc

    try:
        config = Config.model_validate(raw)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}"
            for err in exc.errors()
        )
        raise ConfigError(f"{path}: {details}") from exc

    database = Path(config.users.database)
    if not database.is_absolute():
        config.users.database = str(path.parent / database)

    if config.auth.secret == EXAMPLE_SECRET:
        log.warning("auth.secret is the example value; change it before real use")

    return config
