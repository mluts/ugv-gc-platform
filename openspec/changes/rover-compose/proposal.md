# Proposal

## Why

Every later change (FastAPI, auth, WebSocket, manual control)
is specified against a ground vehicle and tested against a running simulator,
but today the simulator is an ArduCopter quad started by a hand-written `docker run`.

The Compose stack now exists for the video half (MediaMTX and the virtual camera);

the simulated vehicle is the last piece of the simulator layer still outside it,

and nothing above can be built or verified until it is in.

## What Changes

- **BREAKING**: the SITL image builds and runs ArduPilot Rover instead of Copter.
  Copter-only modes (`STABILIZE`, `LAND`, ...) disappear;
  `/stats` reports ground modes (`MANUAL`, `HOLD`, `GUIDED`, ...).
- The ArduPilot tag is pinned to `Rover-4.7.0`.
  It points at the same commit as today's `Copter-4.7.0`,
  so the source tree the bridge was written against does not change, only the vehicle built from it.

  The default frame becomes `rover` (steering + throttle).
- `compose.yaml` gains the simulator as a `sim`-profile service, next to the virtual camera.
  `make up` starts the simulators and MediaMTX; `make sitl` and `make kill` act on the Compose simulator service
  instead of a separate `docker run` container.
- The bridge keeps running on the host (`make run-tcp`), with no container and no image.
  That is the development loop: edit, restart, no rebuild.
- The bridge stays shippable in a container later without code changes:
  its HTTP listen address becomes configurable (it is hard-coded to `127.0.0.1:8080`),
  and its state endpoint answers even when the simulator has never been reachable,
  so it does not depend on start order.
- `scripts/check_sitl.py` (`make check-tcp`) passes against Rover: heartbeat, prearm, armable, mode change, arm.
- README quickstart and API examples describe the Rover stack.

Out of scope:

- A bridge container image and a bridge Compose service. They arrive with the first change that needs them
  (end-to-end tests in `live-telemetry`, or shipping).
- FastAPI, Pydantic models, error codes (`fastapi-api`).
- `MANUAL_CONTROL` and its axis mapping (`manual-drive`).
- The video stack already in `compose.yaml`: no HLS, no stream auth here (`video`).
- Removing `takeoff` / `goto` from `vehicle.py`, renaming the `uav_gc` package, backoff jitter.
- pytest and the SITL session fixture (`fastapi-api` brings the first tests).

## Capabilities

### New Capabilities

- `rover-sitl`: the simulated vehicle is an ArduPilot Rover started from the Compose stack;
  a bridge running on the host reports ground-vehicle state, accepts arm / disarm / mode commands,
  and recovers on its own when the simulator starts late or restarts.

### Modified Capabilities

None. `openspec/specs/` is empty.

## Impact

- `sitl/Dockerfile`, `sitl/entrypoint.sh`: Rover build target, tag, vehicle and frame defaults. The image rebuild is a full ArduPilot clone and compile.
- `compose.yaml`: one new service next to the existing video ones.
- `uav_gc/__main__.py`: listen address from configuration. `uav_gc/link.py`: the state endpoint must answer before the first connection, which it does not today. No endpoint or response-shape change.
- `Makefile`: `up` / `down` / `logs` cover the simulator; `sitl` and `kill` move to Compose; `uav-sitl` / `rm-uav-sitl` give way to `build`.
- `scripts/check_sitl.py`, `README.md`, `.env.example`.

The MAVProxy and check-mode questions are decided in `design.md`.
