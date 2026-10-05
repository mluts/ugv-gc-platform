"""Typed errors raised by vehicle commands.

Each error carries a stable machine-readable ``code`` and a human-readable
``message``. The API layer maps these to HTTP responses by ``code``.
"""


class CommandError(Exception):
    """Base class for command failures."""

    code = "command_error"

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class Rejected(CommandError):
    code = "rejected"


class Timeout(CommandError):
    code = "timeout"


class NoLink(CommandError):
    code = "no_link"


class UnknownMode(CommandError):
    code = "unknown_mode"
