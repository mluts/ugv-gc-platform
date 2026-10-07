# Proposal

## Why

Every remaining capability needs a principal with a role:
the WebSocket handshake carries a token, the stream access check asks who is watching,
and the console must tell a viewer from an operator.
Today the API has no identity at all, so anyone who reaches the port can arm the rover.

Login, JWT, three roles and user management on FastAPI are one of the six requirements,
and `auth-and-roles` is the only unblocked node in `docs/roadmap.md`.

## What Changes

- **BREAKING**: every `/vehicle/*` endpoint requires a bearer token.
  `GET /vehicle/state` needs at least the `viewer` role;
  `POST /vehicle/arm`, `/vehicle/disarm` and `/vehicle/mode` need at least `operator`.
  A request without a valid token answers 401; one with the wrong role answers 403.
  Nothing is sent to the vehicle in either case.
- `POST /auth/login` takes the OAuth2 password form and issues a JWT valid for 30 minutes;
  `GET /auth/me` returns the caller's id, username and role.
- Users live in one SQLite file with argon2 password hashes.
  `GET /users`, `POST /users`, `PATCH /users/{id}` and `DELETE /users/{id}` are admin-only.
  Roles are `viewer`, `operator` and `admin`, each including the rights of the one before.
- The last remaining admin cannot be deleted or demoted,
  so an administrator cannot lock everyone out.
- **BREAKING**: the bridge is configured by one file, `config.toml`, validated at startup:
  listen address, vehicle link, log level, token secret and lifetime, user database and bootstrap admin.
  The `--tcp` / `--udp` / `--serial` flags and the `HTTP_HOST` / `HTTP_PORT` / `LOG_LEVEL` variables go away,
  and `make run` replaces `make run-tcp` and `make run-udp`.
  A missing file, a missing required section, an unknown key or a wrong type stops the bridge with a message naming it.
- On an empty database the bridge creates the first admin from `users.admin_username` and `users.admin_password`;
  it refuses to start with an empty database and no admin credentials,
  and warns while the shipped example secret is in use.
- `.env` becomes optional: `compose.yaml` defaults `LAN_IP` to `127.0.0.1`, so `make up` needs no copy step.
  The file is copied only to override the simulators' settings.
- The error code table grows: `unauthenticated` (401), `forbidden` (403), `invalid_credentials` (401),
  `not_found` (404), `username_taken` (409) and `last_admin` (409).
- `/docs` gains the Authorize button, and the schema declares the security scheme
  and the 401 / 403 responses on every protected route.
- The development loop keeps working with a token:
  `bin/curl-api` reads the listen address and the admin credentials from `config.toml`, logs in and calls an endpoint,
  `make stats` goes through it, and the simulator fixture authenticates before polling.

Out of scope:

- The WebSocket `hello` / `welcome` handshake (`live-telemetry`).
  This change only has to leave a reusable token check behind.
- `GET /media/auth` for nginx `auth_request` (`video`).
- Control ownership and revoking control (`manual-drive`).
- CORS for the Vite dev server (`live-telemetry`).
- Refresh tokens, SSO, lockout, rate limiting, password policy, an action audit.
- Environment-variable overrides of the configuration file;
  `pydantic-settings` can add them if a container setup ever needs them.
- A server container image.

## Capabilities

### New Capabilities

- `auth-and-roles`: login that issues a JWT, three roles with a minimum role per endpoint,
  user management for admins, a bootstrap admin from the configuration file,
  and the error codes a client branches on when a request is unauthenticated or forbidden.

### Modified Capabilities

- `http-api`: the state document and the vehicle commands require a role,
  the failure table gains `unauthenticated` and `forbidden`,
  and the OpenAPI schema declares the security scheme and the 401 / 403 responses.
- `rover-sitl`: the bridge is configured by one validated file instead of flags and environment variables,
  `make run` replaces `make run-tcp`, and `.env` is optional for `make up`.

## Impact

- Depends on `fastapi-api` (archived): the app factory, error handlers and test suites it introduced.
- `uav_gc/api.py`: `require(role)` on the vehicle routes, the auth and user routers, new error handlers.
- New `uav_gc/config.py` (the validated configuration model and its loader),
  `uav_gc/auth.py` (tokens, hashing, role check) and `uav_gc/users.py` (SQLite store).
- `uav_gc/__main__.py`: takes `--config`, builds everything from the file.
  `uav_gc/link.py`: the argument parser is deleted; the connection code is untouched.
- `uav_gc/models.py`, `uav_gc/errors.py`: roles, user and token models, the new error codes.
- `pyproject.toml`, `uv.lock`: `pyjwt`, `argon2-cffi` and `python-multipart` in.
  TOML parsing is the standard library's `tomllib`.
- `tests/`: role fixtures and an in-memory store; every API test gains a token;
  new unit, API and matrix tests; the simulator fixture authenticates.
- `Makefile`: `run` replaces `run-tcp` and `run-udp`; `stats` goes through `bin/curl-api`.
- New `config.example.toml`; `.gitignore` gains `config.toml` and `data/`.
- `compose.yaml`: `LAN_IP` defaults to `127.0.0.1`. `.env.example`: the header says the file is optional.
- `README.md`: quickstart with `config.toml` and `make run`, login before the curl examples,
  the roles table, the new error codes, and how to reset the user database.
- `docs/prod-checklist.md`: change the secret and the admin password before real use.
- Anything calling `/vehicle/*` without a token breaks; in this repository that is `make stats`,
  the README examples and the simulator tests, all updated here.
  Anyone starting the bridge with the old flags must create `config.toml`; the README quickstart says so.
