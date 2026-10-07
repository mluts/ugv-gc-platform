"""Typed API errors.

Each error carries a stable machine-readable ``code`` and a human-readable
``message``. The API layer maps these to HTTP responses by ``code``. The base
classes group the codes by area -- ``CommandError`` for vehicle commands,
``AuthError`` for authentication and authorization, ``UserError`` for user
management -- but the API handles them all through ``ApiError``.
"""

from .models import ErrorCode


class ApiError(Exception):
    """Base class for every failure the API maps to a status and a body."""

    code: ErrorCode

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class CommandError(ApiError):
    """Base class for command failures."""


class Rejected(CommandError):
    code = ErrorCode.rejected


class Timeout(CommandError):
    code = ErrorCode.timeout


class NoLink(CommandError):
    code = ErrorCode.no_link


class UnknownMode(CommandError):
    code = ErrorCode.unknown_mode


class AuthError(ApiError):
    """Base class for authentication and authorization failures."""


class Unauthenticated(AuthError):
    code = ErrorCode.unauthenticated


class Forbidden(AuthError):
    code = ErrorCode.forbidden


class InvalidCredentials(AuthError):
    code = ErrorCode.invalid_credentials


class UserError(ApiError):
    """Base class for user-management failures."""


class NotFound(UserError):
    code = ErrorCode.not_found


class UsernameTaken(UserError):
    code = ErrorCode.username_taken


class LastAdmin(UserError):
    """The last administrator cannot be removed or demoted.

    Named for the condition, not the action, so one error covers both; its
    code is ``last_admin``.
    """

    code = ErrorCode.last_admin
