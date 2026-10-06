# Proposal

## Why

The console and every server change after this one need an API
that is typed, documented, and fails in ways a client can branch on.

Today's aiohttp API returns untyped dicts, answers every failure with 400 and a free-text string,
and has no tests.

FastAPI with REST, OpenAPI and a test suite is also one of the six requirements,
and auth, the WebSocket and the command queue all build on this layer.

## What Changes

- **BREAKING**: the HTTP layer is rewritten on FastAPI; aiohttp is removed.
- **BREAKING**: endpoints move under `/vehicle/`, and the old paths are gone with no aliases:

  | Today | After |
  | --- | --- |
  | `GET /stats` | `GET /vehicle/state` |
  | `POST /arm` | `POST /vehicle/arm` |
  | `POST /disarm` | `POST /vehicle/disarm` |
  | `POST /mode?newmode=hold` | `POST /vehicle/mode` with body `{"mode": "hold"}` |

- The state response becomes a typed model with the same fields `/stats` has today,
  so the OpenAPI schema describes it exactly.
- Failures get a machine-readable code and a matching HTTP status:
  `rejected`, `timeout`, `no_link`, `unknown_mode`, `invalid_request`, `internal`.
- A command sent while the vehicle link is down fails at once with `no_link`
  instead of waiting for a timeout or crashing with a 500.
- `GET /openapi.json` and `GET /docs` are served, generated from the same models the code uses.
- The link supervisor starts and stops with the application
  instead of a task group in `__main__`.
  `make run-tcp` and `make run-udp` keep working as they do now.
- The first tests arrive: unit, API against a fake vehicle, and integration against the Rover simulator.
  `make test-fast` runs what needs no Docker; `make test` runs everything.
- `scripts/check_sitl.py` becomes the first simulator test;
  the script and `make check` / `make check-tcp` are removed.

Out of scope:

- Login, JWT, roles (`auth-roles`).
- `WS /ws` and telemetry push (`live-telemetry`).
- The command queue: ids, TTL, duplicates, one at a time (`commands`).
  Two commands sent at the same moment can still mix up their acknowledgements, as today.
- `MANUAL_CONTROL` (`manual-drive`).
- Endpoints for `takeoff` / `goto`; they are not exposed today either.
- A server container image, CORS, TypeScript type generation.

## Capabilities

### New Capabilities

- `http-api`: the vehicle bridge over HTTP:
  a typed state document, arm / disarm / mode commands,
  error codes a client can branch on,
  and an OpenAPI description generated from the same models.

### Modified Capabilities

- `rover-sitl`: two scenarios name things this change replaces.
  The check-script scenario becomes the simulator test suite,
  and the listen-address scenario stops naming `/stats`.
  `rover-sitl` is introduced by `rover-compose`, which must be archived before this change is.

## Impact

- Depends on `rover-compose` being applied first:
  the simulator tests need the Rover, and the entry point reuses its `HTTP_HOST` / `HTTP_PORT`.
- `uav_gc/api.py`: rewritten. `uav_gc/__main__.py`: starts uvicorn.
- `uav_gc/vehicle.py`: typed errors instead of `RuntimeError` / `ValueError`,
  a link check before each command, and the state snapshot moves here from `api.py`.
- `uav_gc/link.py`: a way to close the connection on shutdown.
- New `uav_gc/models.py`, `uav_gc/errors.py`, `tests/`.
- `pyproject.toml`, `uv.lock`: `fastapi` and `uvicorn` in, `aiohttp` out;
  `pytest`, `pytest-asyncio`, `httpx` as development dependencies.
- `Makefile`: `test`, `test-fast`; `stats` points at the new path; `check`, `check-tcp` removed.
- `scripts/check_sitl.py` removed. `README.md` updated.
- Anything calling the old paths breaks; in this repository that is the `Makefile` and the README examples.
