# Proposal

## Why

The project declares pyright as a dependency and configures it in `pyproject.toml`, but nothing in the workflow runs it, so type errors accumulate silently and surface only when someone opens an editor. Eight diagnostics currently sit in `uav_gc/api.py` (enum-typed error codes, exception-handler signatures, the `responses` dict key type) that runtime coercion hides — and the OpenSpec apply loop, which reports "tests run" per task, has no step that would ever catch them.

## What Changes

- Add a `make typecheck` target that runs pyright, at its default `basic` setting, over the production package `uav_gc`, and make `make test-fast` and `make test` depend on it, so the verification loop always type-checks.
- Fix the eight production diagnostics so the gate is green from the first day — type-only edits, no behavior change.
- Keep the check deliberately loose: the test suite is excluded from pyright, so the duck-typed fakes stay free-form and no production code is reshaped to satisfy a test double.
- Add a project `AGENTS.md` with an always-on rule: this project type-checks production code with pyright; keep it clean and run `make typecheck` before committing.
- Extend `openspec/config.yaml`: add a project `context` naming the stack and the pyright-clean constraint, and amend the `operations.apply.guidance` bullets so each task's stop-and-report includes "`make typecheck` passes".
- No vehicle, API, or wire-format behavior changes; no runtime dependency changes.

## Capabilities

### New Capabilities

- `typechecking`: the project is statically type-checked with pyright — the checker runs as part of verification, the production baseline is clean, and the convention is documented so future changes keep it clean.

### Modified Capabilities

<!-- None: no existing capability's requirements change. -->

## Impact

- `Makefile`: new `typecheck` target; `test-fast` and `test` gain it as a prerequisite.
- `pyproject.toml`: `[tool.pyright]` excludes `tests/`; the checking mode stays the default `basic`.
- `AGENTS.md` (new, project root): the always-on type-checking convention.
- `openspec/config.yaml`: new `context` field; extended `operations.apply.guidance`.
- `uav_gc/api.py`, `uav_gc/errors.py`: type-only fixes for the eight production diagnostics.
- No changes to the tests, dependencies, the HTTP API, the bridge, or the simulator workflows.