# Design

## Context

See proposal.md — Why. Relevant current state:

- pyright is a declared dependency and `[tool.pyright]` exists in `pyproject.toml`, but nothing runs it; `make test-fast` and `make test` run only pytest.
- 8 diagnostics today, all in `uav_gc/api.py` (enum-typed error codes, exception-handler signatures, the `responses` dict key type). The checker runs at its default `basic` setting — `pyproject.toml` sets no `typeCheckingMode` — so this is the gradual middle, not strict mode.
- `errors.py` declares `code = "<literal>"` class attributes (inferred `str`); `models.ErrorCode` is a `str, Enum`; `api.py` passes both `exc.code` and bare literals into `ErrorBody(code=...)`.

## Goals / Non-Goals

Goals:

- A deterministic, always-runnable gate: `make typecheck` is green on the checked-in tree.
- Verification runs the gate: `make test-fast` and `make test` fail if type checking fails.
- The convention is written where agents actually read it: project `AGENTS.md` and the OpenSpec apply guidance.
- The check stays lenient: default `basic` mode, production code only, no annotations for their own sake.

Non-Goals:

- No behavior change to the vehicle, the HTTP API, or the wire format.
- No `strict` mode, and no reshaping of idiomatic Python (duck-typed test doubles) to satisfy the checker.
- No CI, no pre-commit hooks (there is no CI today; a make target fits the project's verification style).
- No new runtime dependencies; the checker stays venv-pinned to the declared version.

## Decisions

### D1: The Makefile is the gate; prose is secondary

Add a `typecheck` target that runs the venv's pyright over the production package, and make `test-fast` and `test` depend on it:

```make
typecheck:
	./.venv/bin/pyright uav_gc

test-fast: typecheck
	PYTHONPATH=. ./.venv/bin/python3 -m pytest -m "not sitl"

test: typecheck
	PYTHONPATH=. ./.venv/bin/python3 -m pytest
```

Add `exclude = ["tests"]` to `[tool.pyright]` so the editor agrees with the CLI and stops reporting diagnostics in the test files. Running `./.venv/bin/pyright` keeps the checker at the version pinned by the dependency, so the gate doesn't drift with editor-installed versions. The checking mode is left at the default `basic`.

*Alternatives considered*: relying on the editor (the status quo that failed), a CI step (no CI exists), or an AGENTS.md-only rule (advisory; an agent can skip it). A make target runs the same way every time and hooks the existing verification entry point.

### D2: Fix the eight production diagnostics; leave the tests free

The gate covers `uav_gc`, so green means zero production errors. All eight are in `uav_gc/api.py`; the `errors.py` fix in D3 is what clears the first of them. The 22 diagnostics in `tests/` are deliberately left alone: they are friction between duck-typed fakes and the checker, not bugs, and reshaping the tests (or production) to satisfy them is exactly the ceremony this change rejects. Tests are excluded from the checker instead.

### D3: `ErrorCode` becomes the type of the error `code` attribute

- In `errors.py`, declare the base attribute as `code: ErrorCode` (annotation only) and set each subclass to an enum member (`code = ErrorCode.rejected`, etc.), importing `ErrorCode` from `models.py`. `models.py` imports nothing from the package, so there is no cycle.
- The base's previous `code = "command_error"` value is dropped: `ErrorCode` has no `command_error` member, nothing reads the attribute, and a bare `CommandError` is never raised (`_STATUS` has no such key). The annotation is what makes `exc.code` an `ErrorCode` at base-typed call sites.
- In `api.py`, use `models.ErrorCode.invalid_request` and `models.ErrorCode.internal` for the synthetic codes.

Then `exc.code` is an `ErrorCode` at the handler, both literal sites are members, and `_STATUS` lookups keep working because `ErrorCode` subclasses `str` (same hash and equality as the plain-string keys).

*Alternative*: coerce at the call sites with `models.ErrorCode(exc.code)`. Rejected — it leaves the class attribute a bare `str`, so every future call site has to remember to coerce. Typing the attribute once fixes the whole chain.

### D4: `add_exception_handler` registrations use a scoped ignore

Starlette types the handler parameter as a union of protocols that receive base `Exception` (`starlette/types.py:24-26`), so the precisely-typed handlers don't assign directly — a stub limitation, not a code problem. Add a scoped, documented ignore on the two registrations:

```python
# NOTE: Starlette types the handler's `exc` as the base `Exception`, so these
# narrower handlers trip reportArgumentType (contravariant parameter).
# See .venv/lib/python3.13/site-packages/starlette/types.py:24-26.
app.add_exception_handler(errors.CommandError, _command_error_handler)  # pyright: ignore[reportArgumentType]
app.add_exception_handler(RequestValidationError, _validation_error_handler)  # pyright: ignore[reportArgumentType]
```

`# pyright: ignore[reportArgumentType]` rather than `# type: ignore[arg-type]`: pyright scopes the former to the named rule; `# type: ignore[...]` suppresses every diagnostic on the line.

*Alternatives*: `cast(ExceptionHandler, ...)` (imports machinery for a checker-only concern — rejected); widening the handler parameters to `Exception` with an `isinstance` re-raise (runtime noise — rejected).

### D5: `_ERROR_RESPONSES` gets an annotation

Annotate `_ERROR_RESPONSES: dict[int | str, dict[str, Any]]` (import `Any`), fixing the three `responses=` invariance errors. This is the one place a small annotation is clearly clearer than a suppression.

### D6: The written convention

- New project-root `AGENTS.md` (distinct from the user's global `~/.config/opencode/AGENTS.md`): states pyright type-checks the production code (default `basic` mode), `make typecheck` must pass before a commit, and `make test-fast` and `make test` include it.
- `openspec/config.yaml`: add a `context:` block naming the stack and the pyright-clean constraint, and amend `operations.apply.guidance` so the stop-and-report bullet reads "...files changed, what/why, tests run, and `make typecheck` passing."

## Risks / Trade-offs

- [Excluding tests means a type error inside a test file is never caught] → Mitigation: accepted by design; tests lean on duck typing, and the production contract they exercise is checked on the production side. A scoped `# type: ignore` remains available if a test genuinely needs one.
- [Starlette's `ExceptionHandler` type changes upstream, making the ignore stale] → Mitigation: the ignore is scoped to two lines with `reportArgumentType`; if the signature is fixed, an unused-ignore warning surfaces it.
- [A future pyright version reports new errors and breaks the gate] → Mitigation: the gate runs the venv-pinned version; upgrades happen deliberately through `uv` and include fixing whatever they flag.
- [`test-fast` runs pyright on every test invocation, adding a few seconds] → Mitigation: acceptable; it is the point of the change, and `typecheck` alone remains available for quick iterations.

## Migration Plan

1. Apply the tasks in order; each task's verify step includes `make typecheck`.
2. After all tasks: `make typecheck`, `make test-fast` and `make test` pass on a clean tree; `openspec validate pyright-typecheck --strict` passes.
3. Rollback is per-commit revert; there is no runtime deployment, data, or schema to migrate.