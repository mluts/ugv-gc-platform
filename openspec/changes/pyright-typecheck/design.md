# Design

## Context

See proposal.md — Why. Relevant current state:

- pyright is a declared dependency and `[tool.pyright]` exists in `pyproject.toml`, but nothing runs it; `make test-fast` runs only pytest.
- 31 diagnostics today: 8 in `uav_gc/api.py` (the ones the user sees in the editor), 1 in `uav_gc/__main__.py` (stale `Api` import), 22 in `tests/` (untyped fake fields, a scripted link that does not match `Vehicle`'s `MavLink` parameter, optional-member access).
- The `fastapi-api` change is in flight: its task 3.5 rewrites `uav_gc/__main__.py` to `uvicorn.run`, and 3.4 adds the supervisor lifespan — both prerequisites for `__main__.py` to type-check.
- `errors.py` declares `code = "<literal>"` class attributes (inferred `str`); `models.ErrorCode` is a `str, Enum`; `api.py` passes both `exc.code` and bare literals into `ErrorBody(code=...)`.

## Goals / Non-Goals

Goals:

- A deterministic, always-runnable gate: `make typecheck` is green on the checked-in tree.
- Verification runs the gate: `make test-fast` fails if type checking fails.
- The convention is written where agents actually read it: project `AGENTS.md` and the OpenSpec apply guidance.

Non-Goals:

- No behavior change to the vehicle, the HTTP API, or the wire format.
- No CI, no pre-commit hooks (there is no CI today; a make target fits the project's verification style).
- No new runtime dependencies; the checker stays venv-pinned to the declared version.

## Decisions

### D1: The Makefile is the gate; prose is secondary

Add a `typecheck` target that runs the venv's pyright over `uav_gc` and `tests`, and make `test-fast` depend on it:

```make
typecheck:
	./.venv/bin/pyright uav_gc tests

test-fast: typecheck
	PYTHONPATH=. ./.venv/bin/python3 -m pytest -m "not sitl"
```

Running `./.venv/bin/pyright` keeps the checker at the version pinned by the dependency, so the gate doesn't drift with editor-installed versions.

*Alternatives considered*: relying on the editor (the status quo that failed), a CI step (no CI exists), or an AGENTS.md-only rule (advisory; an agent can skip it). A make target runs the same way every time and hooks the existing verification entry point.

### D2: Fix all 31 diagnostics, not just the 8 in api.py

The gate covers `uav_gc` and `tests`, so green means zero errors. 23 more exist beyond the editor-visible 8. All fixes are type-only except `__main__.py`, which is coordinated with fastapi-api (D7).

### D3: `ErrorCode` becomes the type of the error `code` attribute

- In `errors.py`, type each class attribute with the enum: `code: ErrorCode = ErrorCode.rejected` (etc.), importing `ErrorCode` from `models.py`. `models.py` imports nothing from the package, so there is no cycle.
- In `api.py`, use `models.ErrorCode.invalid_request` and `models.ErrorCode.internal` for the synthetic codes.

Then `exc.code` is an `ErrorCode`, both literal sites are members, and `_STATUS` lookups keep working because `ErrorCode` subclasses `str` (same hash and equality as the plain-string keys).

*Alternative*: coerce at the call sites with `models.ErrorCode(exc.code)`. Rejected — it leaves the class attribute a bare `str`, so every future call site has to remember to coerce. Typing the attribute once fixes the whole chain.

### D4: `add_exception_handler` registration via `cast`

Starlette types the handler parameter as a union of protocols that receive base `Exception`, so precisely-typed handlers (line 52–53) don't assign directly. Keep the handlers' precise signatures and register with an explicit cast:

```python
from typing import cast
from starlette.types import ExceptionHandler

app.add_exception_handler(errors.CommandError, cast(ExceptionHandler, _command_error_handler))
```

*Alternatives*: `# type: ignore[arg-type]` (silences the whole check, hides future real errors); widening the handler parameters to `Exception` with an `isinstance` re-raise (runtime noise for a checker-only concern). The cast is scoped to the registration line and self-documenting.

### D5: `Vehicle` takes a link protocol, not the concrete `MavLink`

`Vehicle.__init__(self, link: MavLink)` rejects the test's `ScriptedLink`. Define a `VehicleLink` Protocol in `uav_gc/link.py` covering the surface `Vehicle` (and `command.py`) actually use on the link — `on`, `on_link_up`, `wait_for`, `conn`, `status`, `last_error`, `protocol_version` — and type the constructor parameter with it. `MavLink` satisfies it structurally; `ScriptedLink` gains at most two stub members (`last_error`, `protocol_version`) to satisfy it. Production code stays test-agnostic, and the fake is checked against the real contract.

*Alternatives*: `Vehicle(link: MavLink | ScriptedLink)` (couples production to a test module — rejected); `cast(MavLink, scripted_link)` at every test call site (12 casts, silently unchecked fakes — rejected).

### D6: Small fixes elsewhere

- `tests/fakes.py`: annotate the error fields `Exception | None` so `test_errors.py` can assign `Rejected`, `Timeout`, `NoLink`, `UnknownMode` and `RuntimeError` (they all raise from those fields).
- `tests/unit/test_commands.py`: annotate `ScriptedLink.send_error: Exception | None = None`.
- `tests/unit/test_state.py`: assert the optional members are not `None` before attribute access (`assert state.position is not None`), which narrows the type for the following lines.
- `uav_gc/api.py`: annotate `_ERROR_RESPONSES: dict[int | str, dict[str, Any]]` (import `Any`), fixing the three `responses=` invariance errors.

### D7: `__main__.py` is coordinated with fastapi-api 3.4/3.5

`uav_gc/__main__.py` still imports the removed aiohttp `Api`. Its correct replacement — a lifespan that starts the supervisor, plus `uvicorn.run` — is fastapi-api tasks 3.4 and 3.5, which are not yet applied. This change therefore includes a task that:

- verifies `__main__.py` type-checks if fastapi-api 3.5 has already landed, or
- implements the uvicorn switch (per that change's design) if it has not, and notes for the fastapi-api change that its 3.5 is satisfied.

Either way the gate is green when this change is applied. The proposal's Impact section flags this overlap so it is reconciled explicitly, not silently duplicated.

### D8: The written convention

- New project-root `AGENTS.md` (distinct from the user's global `~/.config/opencode/AGENTS.md`): states pyright is the project type checker, `make typecheck` must pass before a commit, and `make test-fast` includes it.
- `openspec/config.yaml`: add a `context:` block naming the stack and the pyright-clean constraint, and amend `operations.apply.guidance` so the stop-and-report bullet reads "...files changed, what/why, tests run, and `make typecheck` passing."

## Risks / Trade-offs

- [A Protocol in a production signature loosens the link parameter] → Mitigation: the Protocol is defined next to `MavLink` and enumerates the exact surface `Vehicle` uses; `MavLink` itself is type-checked against it, so drift is caught by the gate.
- [Starlette's `ExceptionHandler` type changes upstream, making the cast stale] → Mitigation: the cast is confined to two registration lines; a type change there would itself surface as an error, not a silent bug.
- [A future pyright version reports new errors and breaks the gate] → Mitigation: the gate runs the venv-pinned version; upgrades happen deliberately through `uv` and include fixing whatever they flag.
- [Overlap with fastapi-api 3.4/3.5 produces duplicated or conflicting work] → Mitigation: D7's task is sequenced explicitly and notes the reconciliation for the other change.
- [`test-fast` runs pyright on every test invocation, adding a few seconds] → Mitigation: acceptable; it is the point of the change, and `typecheck` alone remains available for quick iterations.

## Migration Plan

1. Apply the tasks in order; each task's verify step includes `make typecheck` on the affected scope.
2. After all tasks: `make typecheck` and `make test-fast` pass on a clean tree; `openspec validate pyright-typecheck --strict` passes.
3. Rollback is per-commit revert; there is no runtime deployment, data, or schema to migrate.
