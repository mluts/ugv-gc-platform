# Tasks

## 1. Gate and convention

- [x] 1.1 Add the `typecheck` target to the `Makefile` (also in `.PHONY`)
  running `./.venv/bin/pyright uav_gc`, and make `test-fast` and `test` depend
  on it; verify `make typecheck` runs the checker and exits non-zero on today's
  errors, and `make test-fast` fails before pytest runs
- [x] 1.2 Add `exclude = ["tests"]` to `[tool.pyright]` in `pyproject.toml`,
  leaving the checking mode at the default `basic`;
  verify pyright reports no diagnostics for files under `tests/`
- [x] 1.3 Add the project-root `AGENTS.md` stating that pyright type-checks
  production code, `make typecheck` must pass before committing,
  and `make test-fast` and `make test` include it;
  verify the file states the rule
- [x] 1.4 Extend `openspec/config.yaml`: add a `context` block naming the stack
  and the pyright-clean constraint, and amend the `operations.apply.guidance`
  stop-and-report bullet to include "`make typecheck` passes";
  verify `openspec list` still parses the config

## 2. Production diagnostics

- [x] 2.1 Type the `code` class attributes in `uav_gc/errors.py` with
  `models.ErrorCode` (enum members as values), and use
  `models.ErrorCode.invalid_request` / `models.ErrorCode.internal` at the
  two literal sites in `api.py`;
  verify `./.venv/bin/pyright uav_gc` reports no `ErrorCode` argument errors
  and `pytest tests/api` passes
- [x] 2.2 Add a scoped, documented `# pyright: ignore[reportArgumentType]` to the two
  `add_exception_handler` registrations in `api.py`, keeping the handlers'
  precise `exc` signatures;
  verify the two `add_exception_handler` errors are gone and
  `pytest tests/api/test_errors.py` passes
- [x] 2.3 Annotate `_ERROR_RESPONSES: dict[int | str, dict[str, Any]]`;
  verify the three `responses=` errors are gone and `pytest tests/api/test_schema.py` passes

## 3. Integration

- [x] 3.1 Run `make typecheck`, `make test-fast` and `make test` on the full tree;
  verify all exit 0 with no type errors and no test failures
- [x] 3.2 Run `openspec validate pyright-typecheck --strict`;
  verify it passes
