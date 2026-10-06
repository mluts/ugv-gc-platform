# Proposal

## Why

The project declares pyright as a dependency and configures it in `pyproject.toml`, but nothing in the workflow runs it, so type errors accumulate silently and surface only when someone opens an editor. Thirty-one diagnostics currently sit in `uav_gc/` and `tests/` (enum-typed error codes, exception-handler signatures, the `responses` dict key type, fake/scripted test doubles, one stale import) that runtime coercion hides — and the OpenSpec apply loop, which reports "tests run" per task, has no step that would ever catch them.

## What Changes

- Add a `make typecheck` target that runs pyright over `uav_gc` and `tests`, and make `make test-fast` (and the later `make test`) depend on it, so the verification loop always type-checks.
- Fix all 31 current pyright diagnostics so the gate is green from the first day — type-only edits, no behavior change. The one exception is `uav_gc/__main__.py`: its `Api` import has been broken since the FastAPI rewrite, and the fix (the `uvicorn.run` switch) is fastapi-api task 3.5, so this change coordinates with that change rather than duplicating it.
- Add a project `AGENTS.md` with an always-on rule: this project type-checks with pyright; keep it clean and run `make typecheck` before committing.
- Extend `openspec/config.yaml`: add a project `context` naming the stack and the pyright-clean constraint, and amend the `operations.apply.guidance` bullets so each task's stop-and-report includes "`make typecheck` passes".
- No vehicle, API, or wire-format behavior changes; no runtime dependency changes.

## Capabilities

### New Capabilities

- `typechecking`: the project is statically type-checked with pyright — the checker runs as part of verification, the type-clean baseline is restored, and the convention is documented so future changes keep it clean.

### Modified Capabilities

<!-- None: no existing capability's requirements change. -->

## Impact

- `Makefile`: new `typecheck` target; `test-fast` gains it as a prerequisite.
- `AGENTS.md` (new, project root): the always-on type-checking convention.
- `openspec/config.yaml`: new `context` field; extended `operations.apply.guidance`.
- `uav_gc/api.py`, `uav_gc/errors.py`, `uav_gc/__main__.py`: type-only fixes for the current diagnostics.
- `tests/fakes.py`, `tests/api/test_errors.py`, `tests/unit/test_commands.py`, `tests/unit/test_state.py`: type fixes for the fake and scripted-link test doubles.
- `pyproject.toml`: unchanged unless pyright needs a config tweak to cover `tests/` and `typings/` cleanly.
- Coordination: `uav_gc/__main__.py` overlaps with fastapi-api task 3.5 (uvicorn switch); see design.md for how the two changes reconcile.
- No changes to dependencies, the HTTP API, the bridge, or the simulator workflows.
