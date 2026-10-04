# Design

## Context

See `proposal.md` for motivation. The state this design starts from:

- `sitl/Dockerfile` clones ArduPilot at `Copter-4.7.0` and runs `./waf copter`; `sitl/entrypoint.sh` runs `sim_vehicle.py -v ArduCopter` with MAVProxy and `--out udp:host.docker.internal:14550`.
- `make sitl` is `docker run -it --name uav-sitl -p 127.0.0.1:5762:5762`; `make kill` is `docker kill uav-sitl`.
- `compose.yaml` (project `ugv-gc-platform`) has `mediamtx` and a `sim`-profile `sim-camera`. The `Makefile` always passes `--profile sim`.
- The bridge runs on the host with `PYTHONPATH=.`; the project has no build system, so `uav_gc` is not an installed package. `Api.serve` binds `127.0.0.1:8080`. `MavLink.from_args()` owns `argparse` and calls `parse_args()`.
- `link.supervise()` already retries the dial with backoff and catches `OSError`, which covers both "connection refused" and a DNS failure for an absent service.
- `MavLink.protocol_version()` reads `self.conn`, which does not exist until the first successful dial. `/stats` calls it, so it fails with a 500 until the simulator has been reached once. On the host this was invisible because the simulator was always started first.

## Goals / Non-Goals

**Goals:**

- The smallest diff that puts a Rover simulator and the bridge into the existing Compose stack.
- Both working loops stay: the full stack in Compose, and a host-run bridge against a Compose simulator.
- Nothing here needs undoing when `fastapi-api` replaces the HTTP layer.

**Non-Goals:**

- Any change to endpoints, response shapes or error codes.
- Hardening the bridge image (non-root user, multi-stage build); it is a development image.
- A healthcheck-based start order. The bridge's reconnect is the mechanism, and it is part of the spec.

## Decisions

### Rover from the same source: tag `Rover-4.7.0`, target `rover`, frame `rover`
`Rover-4.7.0` and `Copter-4.7.0` are the same commit (`1511f27`), so the bridge keeps talking to the code it was written against. The Dockerfile changes the tag argument, the `waf` target and the frame default; the entrypoint changes `-v ArduCopter` to `-v Rover`. The `rover` frame is steering plus throttle, which matches the `steer` / `throttle` setpoints planned for `manual-drive`.

*Alternative:* `Rover-4.7.1`. Deferred: a point-release bump is a separate one-line change, and mixing it in adds a second variable to a vehicle-type switch.
*Alternative:* `rover-skid`. Rejected: skid steering changes the axis meaning that `manual-drive` assumes.

### Keep MAVProxy; give the simulator service a TTY
The `sitl` service sets `tty: true` and `stdin_open: true`, reproducing today's `docker run -it`, and adds `extra_hosts: host.docker.internal:host-gateway` so the existing `--out udp:host.docker.internal:14550` still resolves. MAVProxy is what fans one vehicle link out to several clients, so `make run-udp` and a second observer such as QGroundControl keep working.

*Alternative:* `sim_vehicle.py --no-mavproxy`. Rejected as the default: it removes the UDP output. It is the fallback if the TTY approach fails in task 1.

### Simulator in the `sim` profile, bridge in the default profile
`sitl` joins `sim-camera` under `profiles: [sim]`; `bridge` sits next to `mediamtx` with no profile, since on real hardware the bridge still runs and only its link target changes. The bridge declares no `depends_on`: Compose rejects a dependency on a service in an inactive profile, and start-order independence is a requirement, not an accident.

### Bridge reaches the simulator over TCP on the Compose network
The `bridge` service runs `python -m uav_gc --tcp sitl:5762`. The existing `host:port` argument check already accepts a service name. `sitl` also publishes `127.0.0.1:5762:5762` for the host-run loop.

### Two loops that never overlap
The simulator's TCP serial port serves one client, and both bridges want host port 8080, so only one bridge runs at a time:

| Loop | Commands | Client on 5762 |
| --- | --- | --- |
| Full stack | `make up` | Compose `bridge` |
| Host-run | `make sitl`, then `make run-tcp` or `make check-tcp` | host process |

`make sitl` becomes `$(COMPOSE) up sitl` (foreground, simulator only). `make kill` becomes `$(COMPOSE) kill sitl`; `make up` brings the simulator back. `make build` runs `$(COMPOSE) build` and replaces `uav-sitl` / `rm-uav-sitl`, which named an image Compose no longer uses.

*Alternative:* a second serial port (5763) for the host. Rejected: two bridges commanding one vehicle is not a state worth supporting.

### HTTP listen address from environment variables
`__main__` reads `HTTP_HOST` (default `127.0.0.1`) and `HTTP_PORT` (default `8080`) and passes them to `Api.serve`, which already takes both as parameters. Compose sets `HTTP_HOST=0.0.0.0` and publishes `127.0.0.1:8080:8080`, so the container listens on all its interfaces while the host exposes loopback only.

*Alternative:* `--http-host` arguments. Rejected: `MavLink.from_args()` owns the parser, so this means restructuring argument handling that `fastapi-api` replaces with uvicorn settings anyway.

### `/stats` answers before the first connection
`MavLink.protocol_version()` returns `None` when no connection has been dialed yet. This is the only code change to bridge behaviour, and it is required by the "bridge starts before the simulator" scenario. Command endpoints called before the first connection are left as they are; error handling for commands belongs to `fastapi-api`.

### Bridge image: `deploy/bridge/Dockerfile`, build context at the repo root
Based on `ghcr.io/astral-sh/uv:python3.13-bookworm-slim`: copy `pyproject.toml` and `uv.lock`, run `uv sync --frozen`, copy `uav_gc/`, and run `python -m uav_gc` from the working directory, mirroring how the host runs it. A `.dockerignore` keeps `.venv`, `.git`, `sitl/`, `docs/` and `openspec/` out of the context. The service has `restart: unless-stopped`, like `sim-camera`.

### `check_sitl.py` arms in `MANUAL`
The script switches to `HOLD`, then to `MANUAL`, arms, and disarms before exiting. Going through `HOLD` makes the mode change real, since the rover is likely to boot in `MANUAL`; arming in `MANUAL` checks the mode the console will drive in; the final disarm leaves the simulator reusable.

*Alternative:* keep `GUIDED`. Rejected: it verifies a mode the console never uses.

## Risks / Trade-offs

- [MAVProxy still exits under Compose despite the TTY] → Task 1 checks this first. Fallback is `--no-mavproxy`, dropping `make run-udp` and `make check` and noting it in the README.
- [`pymavlink` has no wheel for Python 3.13 on the image's platform, so `uv sync` needs a compiler] → Add `build-essential` to the bridge image if the build fails; decided when task 3 runs.
- [The first `make up` compiles ArduPilot and takes many minutes] → `make build` is documented as a separate first step; the 60-second scenario assumes built images.
- [A host-run bridge started while the Compose bridge is up fails on port 8080 or sees no heartbeat] → The README states the two loops; no code guards against it.
- [`pyright` is a runtime dependency and inflates the bridge image] → Accepted here; moving it to a dev group is unrelated cleanup.
- [Arm, disarm and mode return a 500 if called before the first connection] → Existing behaviour, now reachable. Left for `fastapi-api`, which defines the "no link" error code.

## Migration Plan

Remove the old container and image once (`docker rm -f uav-sitl`, `docker image rm uav-sitl`); nothing else carries over. Rollback is reverting the change: the previous `make sitl` flow has no persisted state.
