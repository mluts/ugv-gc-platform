# AGENTS.md

Project-specific instructions for agents working in this repository.

## Type checking

The production package (`uav_gc`) is statically type-checked with **pyright** at
its default `basic` setting. The test suite is excluded in `pyproject.toml`
(`[tool.pyright] exclude`), so duck-typed test doubles stay free-form.

- `make typecheck` runs the checker and must pass before committing.
- `make test-fast` and `make test` depend on `make typecheck`, so a type error
  fails verification before pytest runs.
- Fix production type errors rather than suppressing them; where a third-party
  stub is at fault, use a scoped, documented `# pyright: ignore[rule]` with a
  `NOTE:` comment naming the offending file.

## Shell usage

- Invoke venv executables as `.venv/bin/<tool>` with no `./` prefix — e.g.
  `.venv/bin/pyright uav_gc` and `.venv/bin/pytest -m "not sitl"`. The permission
  allowlist matches `.venv/bin/*` but not `./.venv/bin/*`, so the `./` form trips
  a permission prompt. This does not apply to `make` targets, which are already
  allowlisted.
