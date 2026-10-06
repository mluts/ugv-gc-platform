# Design

## Context

See `proposal.md` for motivation. The state this design starts from, with `rover-compose` applied:

- `uav_gc/api.py` is aiohttp: `snapshot(vehicle, link)` builds a dict with `dataclasses.asdict`,
  and `do_arm` / `do_disarm` / `do_set_mode` catch `RuntimeError`, `ValueError`, `TimeoutError` and answer 400.
- `uav_gc/vehicle.py` raises `RuntimeError` for a refusal, for a missing acknowledgement
  and for "accepted but not confirmed" alike, and `ValueError` for an unknown mode.
  `LinkDown` (from `link.py`) is not caught by the API at all, so a link drop during a command is a 500.
- Nothing checks the link before a command is sent.
- `__main__` runs `link.supervise()` and `api.serve()` in one `TaskGroup`,
  so a crash in either ends the process. `HTTP_HOST` / `HTTP_PORT` set the listen address.
- `link.py` reads the socket with `loop.add_reader`, so it needs the standard asyncio event loop.
- No tests exist; `scripts/check_sitl.py` is the only check.
- The bridge is developed on the host. The simulator is a Compose service on `127.0.0.1:5762`,
  and that port serves one client.

## Goals / Non-Goals

**Goals:**

- A FastAPI app whose schema is exact and whose errors are classified where the knowledge is: in the vehicle layer.
- A seam narrow enough that the API can be tested against a fake with four methods.
- The same entry point and Makefile loop as today.

**Non-Goals:**

- Serialising commands. The `commands` change owns the queue.
- Changing what `link.py` and `command.py` do on the wire.
- A formatter, linter or CI setup.

## Decisions

### Module layout

| File | Holds |
| --- | --- |
| `uav_gc/models.py` | Pydantic models: state, request and response bodies, error body |
| `uav_gc/errors.py` | typed command errors |
| `uav_gc/api.py` | `create_app(vehicle, supervise=None)` and the routes |
| `uav_gc/__main__.py` | argument parsing, wiring, `uvicorn.run` |

### The API depends on four methods of the vehicle
`create_app` takes any object with `state()`, `arm()`, `disarm()` and `set_mode(name)`.
`Vehicle.state()` returns the Pydantic state model and replaces `api.snapshot`,
so the snapshot lives with the telemetry it reads, and the WebSocket change can reuse it.
The dataclasses in `vehicle.py` stay as the internal form, with their monotonic `at`.

*Alternative:* keep `snapshot(vehicle, link)` in the API.
Rejected: a fake would have to imitate the attributes of both `Vehicle` and `MavLink`.

### App factory, started from `__main__`
`python -m uav_gc --tcp ...` is unchanged:
`__main__` builds the link and the vehicle, calls `create_app`, and runs `uvicorn.run(app, host, port)`
with `HTTP_HOST` / `HTTP_PORT`.
The dependency is plain `uvicorn`, not `uvicorn[standard]`, so the event loop stays the stdlib one that `add_reader` was written against.

*Alternative:* a module-level `app` started with the `uvicorn` command line.
Rejected: the link target would have to move to environment variables, and `make run-tcp` would change.

### The application lifespan owns the link
On startup the lifespan starts `supervise()` as a task.
On shutdown it cancels the task and closes the vehicle connection through a new `MavLink.close()`,
so the simulator's single-client port is free for the next process or test.
If the supervisor task ends with an unexpected exception, the error is logged and the server is stopped,
which is what the `TaskGroup` does today: a bridge that can never reconnect must not keep serving.

### Errors are classified in the vehicle layer
`errors.py` defines one base class carrying `code` and `message`, with a subclass per code.
`vehicle.py` raises them from `set_mode`, `arm` and `disarm` — the commands the API exposes — covering every way a command can fail:

| Situation in the command path | Error |
| --- | --- |
| link status is not `UP` when the command starts | `no_link` |
| link is `UP` but the mode map is not available (no vehicle type decoded yet) | `no_link` |
| mode name not in the vehicle's mode map | `unknown_mode` |
| socket error while sending (`OSError`) | `no_link` |
| no `COMMAND_ACK` within the timeout | `timeout` |
| `COMMAND_ACK` received and not accepted | `rejected`, message carries the `MAV_RESULT` name |
| accepted, but mode or armed state not reported in time | `timeout` |
| `LinkDown` raised while waiting for the acknowledgement or the confirmation | `no_link` |

The link check runs before anything is sent, which gives the "fails at once" behaviour.
The acknowledgement result is split on `is_no_response()` (→ `timeout`) versus `is_accepted()`
(→ `rejected`); today's code conflates the two into a single "refused" error.
Timeouts stay at the current 5 seconds for the acknowledgement and 5 for the confirmation.

*Alternative:* classify in the API by matching exception messages. Rejected: the strings are not a contract.

### One error body, mapped in exception handlers
The API registers handlers that turn each typed error into `{code, message}` with its status,
request validation errors into `invalid_request`, and anything else into `internal` with a logged traceback.
Each command route declares these responses, so they appear in the OpenAPI schema with `code` as an enumeration.
The body has the same two fields as the planned WebSocket `error` message.

### Responses keep today's shapes
The state model has exactly the fields `/stats` returns now.
Commands answer `{"armed": bool}` or `{"mode": str}`.
The mode request moves from a query parameter to a JSON body so it is a typed model in the schema.

### Tests: three suites, one runner

```
tests/
  fakes.py        FakeVehicle: records calls, raises a chosen error on demand
  unit/           models, Vehicle.state(), command outcome classification
  api/            FastAPI TestClient + FakeVehicle
  sitl/           marked `sitl`; real Vehicle and MavLink against the simulator
```

- **Unit.** `Vehicle` commands run against a scripted link that returns a chosen acknowledgement, times out or raises `LinkDown`,
  covering every row of the classification table. `state()` takes the current time as a parameter so ages are checked without sleeping.
- **API.** The synchronous `TestClient` with `FakeVehicle`: shapes, every error code and status, validation, the schema, `/docs`, the old paths.
- **Simulator.** A session fixture runs `docker compose --profile sim up -d sitl` (a no-op when it is running),
  starts the app in-process with a real link to `127.0.0.1:5762` through `TestClient`,
  and polls the state endpoint until the link is `UP` and the vehicle is armable.
  It does not stop the simulator afterwards.
  The link-loss test kills and restarts the simulator through Compose, waits for armable again, and runs last.
- **Makefile.** `test-fast` runs `pytest -m "not sitl"`; `test` runs `pytest`.

*Alternative:* tests connect on the simulator's second serial port (5763), so a running bridge does not block them.
Rejected for now: the tests arm and change modes, so they would disturb that bridge's session anyway.

### `check_sitl.py` is replaced, not kept alongside
Its steps (heartbeat, armable, `HOLD` then `MANUAL`, arm, disarm) become the first simulator test, driven over HTTP.
The script and `make check` / `make check-tcp` are deleted, which is why `rover-sitl` gets a delta.

## Risks / Trade-offs

- [The `rover-sitl` delta copies two requirements from `rover-compose`, which is not archived yet]
  → Archive `rover-compose` first. If those requirements are edited before then, re-copy them into this delta.
- [Simulator tests fail when a bridge already holds port 5762]
  → The fixture's timeout message says to stop the running bridge; the README repeats it.
- [Two commands at the same moment can mix up acknowledgements and so be misclassified]
  → Existing behaviour, unchanged here; the `commands` change serialises them.
- [The link-loss test restarts the simulator and adds a few minutes to `make test`]
  → It is one test, runs last, and is excluded from `make test-fast`.
- [`TestClient` runs the app's event loop in a worker thread]
  → The link is created inside the fixture and only touched through HTTP from the test thread.
- [`MAV_RESULT_IN_PROGRESS` is reported as `rejected`]
  → Existing treatment in `vehicle.py`; arm, disarm and mode do not use it on ArduPilot.

## Migration Plan

Callers switch to the new paths; in this repository that is `make stats` and the README.
Rollback is reverting the change.
