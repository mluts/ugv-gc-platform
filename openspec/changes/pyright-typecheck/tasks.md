# Tasks

## 1. Gate and convention

- [ ] 1.1 Add the `typecheck` target to the `Makefile` (also in `.PHONY`)
  running `./.venv/bin/pyright uav_gc tests`, and make `test-fast` depend on it;
  verify `make typecheck` runs the checker and exits non-zero on today's errors,
  and `make test-fast` fails before pytest runs
- [ ] 1.2 Add the project-root `AGENTS.md` stating that pyright is the project
  type checker, `make typecheck` must pass before committing,
  and `make test-fast` includes it;
  verify the file states the rule
- [ ] 1.3 Extend `openspec/config.yaml`: add a `context` block naming the stack
  and the pyright-clean constraint, and amend the `operations.apply.guidance`
  stop-and-report bullet to include "`make typecheck` passes";
  verify `openspec list` still parses the config

## 2. api.py and errors.py diagnostics

- [ ] 2.1 Type the `code` class attributes in `uav_gc/errors.py` with
  `models.ErrorCode` (enum members as values), and use
  `models.ErrorCode.invalid_request` / `models.ErrorCode.internal` at the
  two literal sites in `api.py`;
  verify `./.venv/bin/pyright uav_gc/api.py uav_gc/errors.py` reports no
  `ErrorCode` argument errors and `pytest tests/api` passes
- [ ] 2.2 Register the command-error and validation-error handlers with
  `cast(ExceptionHandler, ...)` from `starlette.types`, keeping their precise
  `exc` signatures;
  verify the two `add_exception_handler` errors are gone and
  `pytest tests/api/test_errors.py` passes
- [ ] 2.3 Annotate `_ERROR_RESPONSES: dict[int | str, dict[str, Any]]`;
  verify the three `responses=` errors are gone and `pytest tests/api/test_schema.py` passes

## 3. Test doubles and test code

- [ ] 3.1 Annotate the `arm_error` / `disarm_error` / `set_mode_error` fields in
  `tests/fakes.py` as `Exception | None`;
  verify `./.venv/bin/pyright tests/api/test_errors.py` is clean and the tests pass
- [ ] 3.2 Add a `VehicleLink` protocol in `uav_gc/link.py` covering the link
  surface `Vehicle` uses, type `Vehicle.__init__` with it, and make
  `ScriptedLink` satisfy it (adding the missing stubs and typing `send_error`
  as `Exception | None`);
  verify `./.venv/bin/pyright tests/unit/test_commands.py uav_gc/vehicle.py`
  is clean and `pytest tests/unit/test_commands.py` passes
- [ ] 3.3 Narrow the optional state members in `tests/unit/test_state.py` with
  `assert ... is not None` before attribute access;
  verify `./.venv/bin/pyright tests/unit/test_state.py` is clean and the tests pass

## 4. __main__.py coordination with fastapi-api

- [ ] 4.1 If fastapi-api tasks 3.4 and 3.5 have already landed, verify
  `uav_gc/__main__.py` type-checks as-is; otherwise implement the uvicorn
  switch per fastapi-api's design (lifespan starts the supervisor,
  `uvicorn.run` honors `HTTP_HOST` / `HTTP_PORT`) and note in that change's
  tasks that 3.5 is satisfied;
  verify `./.venv/bin/pyright uav_gc/__main__.py` is clean and
  `PYTHONPATH=. ./.venv/bin/python3 -m uav_gc --help` starts

## 5. Integration

- [ ] 5.1 Run `make typecheck` and `make test-fast` on the full tree;
  verify both exit 0 with no type errors and no test failures
- [ ] 5.2 Run `openspec validate pyright-typecheck --strict`;
  verify it passes
