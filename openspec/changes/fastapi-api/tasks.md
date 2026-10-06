# Tasks

## 1. Dependencies and test scaffolding

- [x] 1.1 Add `fastapi` and `uvicorn`, remove `aiohttp`,
  and add `pytest`, `pytest-asyncio` and `httpx` as development dependencies;
  verify `uv sync` succeeds and `python -c "import fastapi, uvicorn"` runs in the venv
- [x] 1.2 Add pytest settings to `pyproject.toml` (`pythonpath`, `asyncio_mode = "auto"`, the `sitl` marker)
  and create `tests/unit`, `tests/api`, `tests/sitl`;
  verify `pytest --markers` lists `sitl`

## 2. State model and typed errors

- [x] 2.1 Add the Pydantic state models to `uav_gc/models.py`
  and `Vehicle.state(now)` returning them, replacing `api.snapshot`;
  verify with unit tests for the empty state (nulls, no batteries) and for ages computed from a given time
- [x] 2.2 Add `uav_gc/errors.py` and raise the typed errors from `set_mode`, `arm` and `disarm`
  per the classification table in `design.md`, including the link check before sending and
  the `is_no_response()` / `is_accepted()` split; verify with unit tests against a scripted
  link, one per table row, and that nothing is sent when the link is down
- [x] 2.3 Add `make test-fast`; verify it passes with Docker stopped

## 3. FastAPI application

- [x] 3.1 Rewrite `uav_gc/api.py` as `create_app(vehicle, supervise=None)`
  with `GET /vehicle/state` and `POST /vehicle/arm`, `/vehicle/disarm`, `/vehicle/mode`,
  add `tests/fakes.py` with `FakeVehicle`;
  verify with API tests for the state shape, each command's success body, case-insensitive mode,
  and 404 on `/stats`, `/arm`, `/disarm`, `/mode`
- [x] 3.2 Add the error body model and the exception handlers;
  verify with API tests that each of `rejected`, `timeout`, `no_link`, `unknown_mode`, `invalid_request` and `internal`
  returns its status and `{code, message}`, and that `internal` leaks no traceback
- [x] 3.3 Declare the error responses on the command routes;
  verify with API tests that `/openapi.json` lists the four paths, types `link.status` and the error `code` as enumerations,
  and that `/docs` returns 200
- [ ] 3.4 Add `MavLink.close()` and the lifespan that starts the supervisor, closes the link on shutdown
  and stops the server if the supervisor crashes;
  verify with API tests that the supervisor callable is started and cancelled around the client's lifetime
- [ ] 3.5 Switch `uav_gc/__main__.py` to `uvicorn.run` with `HTTP_HOST` / `HTTP_PORT` and delete the aiohttp code;
  verify `make run-tcp` against the simulator serves `/vehicle/state` and `/docs`,
  and that with no simulator running `POST /vehicle/arm` answers 503 `no_link` at once
- [ ] 3.6 Point `make stats` at `/vehicle/state` and update the README API section:
  the paths, the JSON body for mode, the error code table and `/docs`;
  verify every `curl` example in the README runs as written

## 4. Simulator tests

- [ ] 4.1 Add the session fixture in `tests/sitl/conftest.py`: start the simulator through Compose,
  run the app in-process against `127.0.0.1:5762`, wait for link `UP` and `armable`,
  and fail with a message naming a possibly connected bridge on timeout;
  verify `pytest -m sitl` reaches the first test with the simulator both stopped and already running
- [ ] 4.2 Port `scripts/check_sitl.py` to a simulator test over HTTP:
  a Rover mode in the state, `HOLD` then `MANUAL`, arm, disarm, and `land` answering `unknown_mode`;
  delete the script and the `check` / `check-tcp` targets;
  verify the test passes
- [ ] 4.3 Add the link-loss test, ordered last: kill the simulator, expect the link not `UP` within 10 seconds
  and `POST /vehicle/arm` answering `no_link` within 1 second, restart it, expect `UP` and `armable` again;
  verify the test passes and leaves the simulator running
- [ ] 4.4 Add `make test` and a README testing section covering both targets
  and the need to stop a running bridge first;
  verify `make test` passes with no bridge connected

## 5. Integration

- [ ] 5.1 Verify from a clean clone: `uv sync`, `make build`, `make test` passes
- [ ] 5.2 Run `openspec validate fastapi-api --strict` and verify it passes
