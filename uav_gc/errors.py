"""Typed errors raised by vehicle commands.

Each error carries a stable machine-readable ``code`` and a human-readable
``message``. The API layer maps these to HTTP responses by ``code``.
"""

from .models import ErrorCode


class CommandError(Exception):
    """Base class for command failures."""

    code: ErrorCode

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class Rejected(CommandError):
    code = ErrorCode.rejected


class Timeout(CommandError):
    code = ErrorCode.timeout


class NoLink(CommandError):
    code = ErrorCode.no_link


class UnknownMode(CommandError):
    code = ErrorCode.unknown_mode
