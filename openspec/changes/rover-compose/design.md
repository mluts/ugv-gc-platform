# Design

## Context

See `proposal.md` for motivation. The state this design starts from:

- `sitl/Dockerfile` clones ArduPilot at `Copter-4.7.0` and runs `./waf copter`; `sitl/entrypoint.sh` runs `sim_vehicle.py -v ArduCopter` with MAVProxy and `--out udp:host.docker.internal:14550`.
- `make sitl` is `docker run -it --name uav-sitl -p 127.0.0.1:5762:5762`; `make kill` is `docker kill uav-sitl`.
- `compose.yaml` (project `ugv-gc-platform`) has `mediamtx` and a `sim`-profile `sim-camera`. The `Makefile` always passes `--profile sim`.
- The bridge runs on the host with `PYTHONPATH=.`. `Api.serve` binds `127.0.0.1:8080`. `MavLink.from_args()` owns `argparse` and calls `parse_args()`.
- `link.supervise()` already retries the dial with backoff and catches `OSError`.
- `MavLink.protocol_version()` reads `self.conn`, which does not exist until the first successful dial. `/stats` calls it, so it fails with a 500 when the bridge is started before the simulator.

## Goals / Non-Goals

**Goals:**

- The smallest diff that puts a Rover simulator into the existing Compose stack.
- The bridge is developed on the host: edit, restart, no image rebuild.
- Nothing in the bridge prevents packing it into a container later.

**Non-Goals:**

- A bridge image or a bridge Compose service.
- Any change to endpoints, response shapes or error codes.

## Decisions

### Rover from the same source: tag `Rover-4.7.0`, target `rover`, frame `rover`
`Rover-4.7.0` and `Copter-4.7.0` are the same commit (`1511f27`), so the bridge keeps talking to the code it was written against. The Dockerfile changes the tag argument, the `waf` target and the frame default; the entrypoint changes `-v ArduCopter` to `-v Rover`. The `rover` frame is steering plus throttle, which matches the `steer` / `throttle` setpoints planned for `manual-drive`.

*Alternative:* `Rover-4.7.1`. Deferred: a point-release bump is a separate one-line change, and mixing it in adds a second variable to a vehicle-type switch.
*Alternative:* `rover-skid`. Rejected: skid steering changes the axis meaning that `manual-drive` assumes.

### Simulator is a `sim`-profile Compose service
`sitl` joins `sim-camera` under `profiles: [sim]`, built from `./sitl`, publishing `127.0.0.1:5762:5762`. `SITL_SPEEDUP` passes through from `.env`.

Makefile:

| Target | Does |
| --- | --- |
| `up` | simulator, MediaMTX and camera in the background |
| `sitl` | `$(COMPOSE) up sitl`: simulator only, in the foreground |
| `kill` | `$(COMPOSE) kill sitl`; `make up` brings it back |
| `build` | `$(COMPOSE) build`; replaces `uav-sitl` / `rm-uav-sitl` |
| `run-tcp`, `check-tcp` | unchanged, against `127.0.0.1:5762` |

### Keep MAVProxy; give the simulator service a TTY
The `sitl` service sets `tty: true` and `stdin_open: true`, reproducing today's `docker run -it`, and adds `extra_hosts: host.docker.internal:host-gateway` so the existing `--out udp:host.docker.internal:14550` still resolves. MAVProxy is what fans one vehicle link out to several clients, so `make run-udp` and a second observer such as QGroundControl keep working.

*Alternative:* `sim_vehicle.py --no-mavproxy`. Rejected as the default: it removes the UDP output. It is the fallback if the TTY approach fails in task 1.2.

### Bridge runs on the host; the container is deferred, not designed out
No image is built here. What keeps a container possible later is that the bridge takes everything environment-specific from outside:

- **Link target:** already an argument (`--tcp host:port`), and the check accepts a service name such as `sitl:5762`.
- **Listen address:** made configurable in this change (next decision).
- **Start order:** the bridge must not need the simulator to exist first (decision after that).
- **Files:** it reads nothing from host paths.

*Alternative:* add the image and service now. Rejected: nothing before `live-telemetry` needs it, and `fastapi-api` rewrites the entry point the image would start.

### HTTP listen address from environment variables
`__main__` reads `HTTP_HOST` (default `127.0.0.1`) and `HTTP_PORT` (default `8080`) and passes them to `Api.serve`, which already takes both as parameters. The loopback default matters because the API has no auth until `auth-roles`.

*Alternative:* `--http-host` arguments. Rejected: `MavLink.from_args()` owns the parser, so this means restructuring argument handling that `fastapi-api` replaces with uvicorn settings anyway.

### `/stats` answers before the first connection
`MavLink.protocol_version()` returns `None` when no connection has been dialed yet. Command endpoints called before the first connection are left as they are; error handling for commands belongs to `fastapi-api`.

### `check_sitl.py` arms in `MANUAL`
The script switches to `HOLD`, then to `MANUAL`, arms, and disarms before exiting. Going through `HOLD` makes the mode change real, since the rover is likely to boot in `MANUAL`; arming in `MANUAL` checks the mode the console will drive in; the final disarm leaves the simulator reusable.

*Alternative:* keep `GUIDED`. Rejected: it verifies a mode the console never uses.

## Risks / Trade-offs

- [MAVProxy still exits under Compose despite the TTY] → Task 1.2 checks this first. Fallback is `--no-mavproxy`, dropping `make run-udp` and `make check` and noting it in the README.
- [The first `make up` compiles ArduPilot and takes many minutes] → `make build` is documented as a separate first step; the timing scenarios assume built images.
- [The simulator's TCP port serves one client, so the bridge and `make check-tcp` cannot run together] → The README says to stop the bridge before running the check.
- [`make up` no longer gives a working API on its own; the bridge needs a second command] → Accepted for the development loop; revisited when the bridge image lands.
- [Arm, disarm and mode return a 500 if called before the first connection] → Existing behaviour. Left for `fastapi-api`, which defines the "no link" error code.

## Migration Plan

Remove the old container and image once (`docker rm -f uav-sitl`, `docker image rm uav-sitl`); nothing else carries over. Rollback is reverting the change: the previous `make sitl` flow has no persisted state.
