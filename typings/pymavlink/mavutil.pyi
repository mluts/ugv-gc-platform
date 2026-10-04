"""Hand-written partial stub for pymavlink.mavutil.
"""

from typing import Any

from pymavlink.dialects.v20 import ardupilotmega

mavlink = ardupilotmega

class mavfile:
    mav: ardupilotmega.MAVLink
    target_system: int
    target_component: int
    WIRE_PROTOCOL_VERSION: str
    sysid: int
    def wait_heartbeat(
        self, blocking: bool = ..., timeout: float | None = ...
    ) -> Any: ...
    def recv_match(
        self,
        condition: str | None = ...,
        type: str | list[str] | None = ...,
        blocking: bool = ...,
        timeout: float | None = ...,
    ) -> Any: ...
    def close(self) -> None: ...
    def __getattr__(self, name: str) -> Any: ...

# NOTE: can also return DFReader/CSVReader for log files; annotated with the
# live-connection base class only
def mavlink_connection(
    device: str,
    baud: int = ...,
    source_system: int = ...,
    source_component: int = ...,
    dialect: str = ...,
    autoreconnect: bool = ...,
    retries: int = ...,
    **opts: Any,
) -> mavfile: ...
def __getattr__(name: str) -> Any: ...
