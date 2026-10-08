# AGENTS.md

Project-specific instructions for agents working in this repository.

## Type checking

- Static type-checking is done with **pyright**
- The test suite is excluded in `pyproject.toml` (`[tool.pyright] exclude`)
- `make typecheck` runs the checker.
- `make test-fast` and `make test` depend on `make typecheck`
- Fix type errors rather than suppressing them; where a third-party
  stub is at fault, use a scoped, documented `# pyright: ignore[rule]` with a
  `NOTE:` comment naming the offending file.

## Shell usage

- Invoke venv executables as `.venv/bin/<tool>` with no `./` prefix — e.g.
  `.venv/bin/pyright uav_gc` and `.venv/bin/pytest -m "not sitl"`.
- Reach the bridge's HTTP API only through `bin/curl-api <path>`: it reads
  `config.toml`, logs in and attaches the token, and `make stats` goes through it.
  Never call raw `curl` against the API — it is not allowlisted, and with auth
  enforced it just answers 401. Use `bin/curl-api --no-auth` for the deliberately
  unauthenticated case.

## Design: partial abstractions

- Prefer partial abstractions that make the right path easy and the wrong
  path awkward over insisting on complete, tamper-proof enforcement. The
  useful question is "does this eliminate the likely mistake and signal
  intent?", not "can this be defeated?".
- Don't evaluate a guard by adversarial bypass. The realistic failure here
  is accidental misuse, not sabotage; anyone determined to bypass a guard
  can just edit the file.
- Reserve hard guarantees for silent-and-severe failures: security
  boundaries, or invariants whose violation corrupts data irreversibly. For
  everything else, convention plus a good abstraction is the correct level
  of protection.
