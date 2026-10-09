# Design

## Context

See `proposal.md` for motivation. The state this design starts from, with `fastapi-api` and `pyright-typecheck` applied:

- `uav_gc/api.py` is `create_app(vehicle, supervise=None)`: four routes, no `Depends` callables on them,
  and three exception handlers keyed on `errors.CommandError`, `RequestValidationError` and `Exception`.
  A status table in the module maps each error code to its HTTP status.
- `uav_gc/errors.py` has one base `CommandError` carrying `code` and `message`, with a subclass per code.
  `uav_gc/models.py` holds the `ErrorCode` enumeration and the `ErrorBody`.
- `uav_gc/__main__.py` reads `HTTP_HOST`, `HTTP_PORT` and `LOG_LEVEL` from the environment
  and builds the link through `MavLink.from_args()`, which parses `--tcp`, `--udp`, `--serial` and `--baud`
  into the constructor `MavLink(dev, baud)` that the simulator fixture already calls directly.
- The server runs on the host via `make run-tcp`.
  `.env` is read by Compose only, and `compose.yaml` defaults every variable in it except `LAN_IP`.
- MediaMTX is configured by `deploy/mediamtx/mediamtx.yml`, a file mounted read-only into its container.
- The API tests build the app with `FakeVehicle` through a `_client()` helper per file;
  the simulator fixture builds the app with a real link and polls `GET /vehicle/state` until armable.
- `bin/` holds curl wrappers for MediaMTX; `make stats` curls the state endpoint directly.
- The command routes are `async` and await the vehicle; the state route is sync. `link.py` needs the stdlib event loop.

## Goals / Non-Goals

**Goals:**

- No unauthenticated mode exists: the app cannot be built without a user store and a secret.
- A token check small enough for the WebSocket handshake to reuse unchanged.
- The authorization decision reads the user's current role, so revocation is immediate.
- One configuration file for the bridge, validated before the link or the listener is opened.
- Tests cover the role matrix without the simulator, with a fake vehicle and an in-memory store.

**Non-Goals:**

- Token revocation lists, refresh tokens, sessions.
- Environment-variable overrides of the configuration file.
- Protecting MediaMTX; that arrives with `video`.
- Any change to what `link.py`, `command.py` and `vehicle.py` do on the wire.

## Decisions

### Module layout

| File | Holds |
| --- | --- |
| `uav_gc/config.py` | `Config`, the Pydantic model of the file with sections `http`, `link`, `log`, `auth`, `users`; `load_config(path)`; the example-secret constant |
| `uav_gc/auth.py` | `Role` ordering, `hash_password` / `verify_password` taking the hasher, `TokenCodec`, and `Auth(users, codec, hasher)` with `authenticate`, `authorize` and `require(role)`, the `Depends` callable for routes |
| `uav_gc/users.py` | `UserStore`: the SQLite table, CRUD, the last-admin rule, bootstrap; it stores hashes and never computes them |
| `uav_gc/models.py` | `Role`, `User`, `UserCreate`, `UserUpdate`, `Token`, the new error codes |
| `uav_gc/errors.py` | an `ApiError` base; `CommandError`, `AuthError` and `UserError` under it |
| `uav_gc/api.py` | `create_app(vehicle, supervise=None, *, users, auth)`, the auth and user routes, `require(role)` on the vehicle routes |
| `uav_gc/__main__.py` | `--config`, loads and validates the file, opens the store, bootstraps, builds the link and the app, fails fast |

### One error base, one handler, one status table
`ApiError` carries `code` and `message`; `CommandError` keeps its subclasses and becomes a child of it,
as do `AuthError` (`Unauthenticated`, `Forbidden`, `InvalidCredentials`) and `UserError` (`NotFound`, `UsernameTaken`, `LastAdmin`).
The status table in `api.py` grows by the six new codes, and the one handler for `ApiError` replaces the one for `CommandError`.
The handler adds `WWW-Authenticate: Bearer` on the two 401 codes.

*Alternative:* a handler per base class. Rejected: three copies of the same five lines.

### One configuration file, validated at startup
The bridge reads `config.toml` from the working directory, or the path given by `--config`.
The file is per-machine and gitignored; `config.example.toml` is committed with working development values,
so `cp config.example.toml config.toml` is the only setup step for the bridge.

| Section | Keys | Default |
| --- | --- | --- |
| `[http]` | `host`, `port` | `127.0.0.1`, `8080` |
| `[link]` | `device` (pymavlink string: `tcp:127.0.0.1:5762`, `udpin:0.0.0.0:14550`, a serial path), `baud` | no default for `device`; `115200` |
| `[log]` | `level` | `INFO` |
| `[auth]` | `secret`, `token_ttl_min` | no default for `secret`; `30` |
| `[users]` | `database`, `admin_username`, `admin_password` | `data/users.db`; the admin keys are optional |

`tomllib` from the standard library parses the file.
A Pydantic model with `extra="forbid"` validates it, so an unknown key, a wrong type, a missing required
section, a missing `device` or an empty `secret` stops the bridge with a message naming the section or key;
a missing file stops it naming the path.
Relative paths resolve against the directory of the configuration file, not the working directory.
Only `users.database` is a filesystem path; `link.device` is a pymavlink device string — a serial device is absolute, under `/dev` — and is passed through unchanged.
The shipped example secret is one named constant in `config.py`; `load_config` logs a warning when it is in use,
and `config.example.toml` quotes the same constant in its comment, so the check and the file cannot drift.
A container mounts the file read-only, exactly as the MediaMTX container mounts its own.

*Alternative:* environment variables fed from `.env` through `-include .env` in the Makefile.
Rejected: `.env` would be parsed by make, by bash in `bin/curl-api` and by Compose, with three different grammars;
a quote, a `#` or a `$` in a password gives three different values and no error.

*Alternative:* YAML, matching the MediaMTX file. Rejected: a new dependency and implicit typing of values like `on` or `1e3`.

*Alternative:* JSON. Rejected: no comments, so the example file cannot explain itself.

*Alternative:* `pydantic-settings` with TOML plus environment overrides.
Not needed yet; it is the upgrade path if a container setup ever needs overrides.

### `.env` goes away; `compose.yaml` defaults every simulator setting
`compose.yaml` already defaults every variable it reads except `LAN_IP`, whose documented default is `127.0.0.1`.
The one-token change `${LAN_IP:-127.0.0.1}` makes `make up` work on a fresh clone with no `.env`.
`.env.example` is deleted rather than reworded: Compose reads an exported variable with higher precedence than
a `.env` file, so the file only ever added persistence — for viewing from another device or looping a camera file —
and the override is just as easy on the command line (`LAN_IP=192.168.1.5 make up`).
The `rover-sitl` delta records it.

### Fail fast on a bad file, a missing section, a missing secret, or an empty store without credentials
`__main__` loads and validates the file before opening the link or the store, and exits with the validator's message on failure.
A missing required section (`[link]`, `[auth]`) is itself a failure: it stops the bridge naming the section, before the link or the store is opened.
Validation failures are rendered from Pydantic's error locations as `path: section.key: message`, so the configuration — including any password in it — is never echoed back.
When the store has no users and either admin key is missing, it exits naming `users.admin_username` and `users.admin_password`.
Bootstrap runs only on an empty store; after that the database is the source of truth and the admin keys are ignored.

*Alternative:* generate a random secret per process when unset.
Rejected: every restart would log everyone out silently, and a half-configured deployment would look healthy.

### Tokens are JWT HS256 with the user id as subject, and the user is looked up on every request
Claims are `sub` (subject: the user id as a string), `iat` (issued at) and `exp` (expiration), the last two as Unix seconds.
No role claim. `Auth.authenticate(token)` decodes the token and loads the user by id into a `User`,
raising `Unauthenticated` for a missing, malformed, expired or forged token or a deleted user;
`Auth.authorize(user, role)` compares the stored role against the required rank and raises `Forbidden`.
Both take the token or the user as a plain argument, with no request object involved,
so the WebSocket `hello` handler in `live-telemetry` calls them with the token from the message body.
`require(role)` is the FastAPI wrapper: it reads the bearer header and calls the two in turn.
A deleted user's token therefore fails at once, and a demotion applies on the next request,
which the spec requires and which the doc's rule "the decision always belongs to the server" implies.
Token lifetime comes from `auth.token_ttl_min`.
The codec calls `now()` when it issues a token and writes the result into `iat` and `now()` plus the lifetime into `exp`.
Decoding compares `exp` with the real system clock; `now` plays no part in it.
Tests make an expired token by issuing it with a `now` set 31 minutes in the past, instead of sleeping.

*Alternative:* carry the role in the token and skip the lookup.
Rejected: revocation would wait up to 30 minutes; one indexed SQLite read per request costs nothing here.

*Alternative:* an opaque session id in a `sessions` table, looked up per request.
Simpler to revoke, and nothing in this deployment forbids it.
Rejected: a signed token is valid without any storage, so the user table stays the only table,
login writes nothing, and expiry travels inside the token instead of in a row that needs cleaning up;
the WebSocket handshake and the nginx access check can later verify a token with nothing but the secret;
and the per-request lookup this design keeps gives immediate revocation for a deleted or demoted user,
which is the case a session would have covered.

### Passwords are argon2id hashes, and the hasher is an argument
`argon2-cffi`'s `PasswordHasher` with its defaults in production: 3 passes over 64 MiB, tens of milliseconds per hash by design.
The hasher is never a module global. `hash_password(hasher, password)` and `verify_password(hasher, hash, password)` take it,
`Auth(users, codec, hasher)` holds the one the app uses, and `UserStore` only stores the resulting strings:
`create` and `bootstrap` take a hash, and the routes and `__main__` hash first.
`__main__` passes `PasswordHasher()`; the test helper passes `PasswordHasher.from_parameters(argon2.profiles.CHEAPEST)`,
the profile the library itself marks as for testing only,
so the fast suite does not pay for some two hundred production-strength hashes per run.
Login verifies against a fixed dummy hash when the username is unknown,
so an unknown name and a wrong password take about the same time and return the same body.

*Alternative:* hash the three fixture passwords once per session and let `create` accept a ready hash.
Rejected: a second code path in production that exists only for tests.

### The user store is `sqlite3` from the standard library, synchronous, behind a lock
One table: `users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL)`,
created with `CREATE TABLE IF NOT EXISTS` when the store opens; the parent directory is created if missing.
The connection is opened with `check_same_thread=False` and every method takes a lock,
because `TestClient` and FastAPI's threadpool call the store from several threads.
`close()` closes the connection, and the application lifespan calls it at shutdown beside `vehicle.link.close()`,
so a clean stop releases both external resources the bridge holds,
and the test client's exit leaves no unclosed connection behind.
The last-admin rule is checked inside the same lock as the delete or update,
so two concurrent requests cannot both pass the count.
`:memory:` is the path for tests.

*Alternative:* an async driver. Rejected: an extra dependency for sub-millisecond queries.
*Alternative:* an ORM with migrations. Out of scope by the doc.

### Sync `Depends` callables and user routes, async vehicle routes
`require(role)` and the auth and user routes are plain `def`, so FastAPI runs them in its threadpool,
where the blocking store call and the argon2 verification belong.
The vehicle routes stay `async` and keep awaiting the vehicle; `require(role)` runs in the threadpool first.

### The bearer is read through FastAPI's OAuth2 password scheme with `auto_error=False`
An instance of FastAPI's `OAuth2PasswordBearer`, constructed with `tokenUrl="/auth/login"` and `auto_error=False`,
is the `Depends` callable that reads the `Authorization` header and returns the token.
FastAPI's schema generator adds the security scheme and each protected route's security requirement
from that callable, and the Swagger UI page served at `/docs` shows the Authorize button
from the schema, so `uav_gc` holds no code for either.
With `auto_error=False` the callable returns `None` for a missing or non-bearer header
instead of raising FastAPI's own 401 with a `{"detail": ...}` body;
`require(role)` treats `None` and an empty token alike and passes them to `authenticate`,
which raises `Unauthenticated` and so answers with the project's `{code, message}` body.
Login takes `OAuth2PasswordRequestForm`, so a missing field is a `RequestValidationError` and lands on the existing `invalid_request` handler.
Protected routes declare the 401 and 403 responses in `responses`, as the command routes already declare theirs.
The app is built with `redoc_url=None`, so the open routes are exactly login, `/openapi.json`, `/docs` and the `/docs/oauth2-redirect` helper
that FastAPI serves with Swagger UI; the spec lists those four and nothing else.

### Roles are an ordered string enumeration
`Role` is a `str` enumeration with values `viewer`, `operator`, `admin`;
a rank table in `auth.py` orders them, and `require(role)` compares ranks.
The matrix in the spec is the single source for which route takes which rank.

### The app factory takes the store and the auth object as required keyword arguments
`create_app(vehicle, supervise=None, *, users, auth)`.
`auth` is the `Auth` instance; `__main__` builds it from the store, a `TokenCodec` made from the file's `[auth]` section and the default hasher,
and tests build it from an in-memory store, a codec with an injected clock, so they can mint expired tokens, and the cheapest hasher.
There is no default, so no test and no entry point can build an app that serves without authentication.
A `make_client` fixture in `tests/conftest.py` returns a factory `make_client(vehicle=None, supervise=None, **client_kwargs)`:
it builds an in-memory store with one user per role and the app, forwards `supervise` to `create_app`
and the keyword arguments to `TestClient`, and returns the client and a `dict[Role, str]` of tokens.
The lifespan tests pass `supervise` and the internal-error test passes `raise_server_exceptions=False`,
so the factory has to take both; being a fixture, it is used without importing `conftest`.
The existing API tests switch to it and otherwise stay as they are.
The simulator fixture builds the same in-memory store with one admin, mints a token through the codec,
and sets the client's default `Authorization` header before polling, so `make test` stays green
from the task that first enforces a role.
The `rover-sitl` scenarios speak of the state endpoint reporting values, not of headers, so those stay as they are.

### `bin/curl-api` reads `config.toml` and logs in on every call
`bin/curl-api <path> [curl options]`: reads `http.host`, `http.port`, `users.admin_username` and `users.admin_password`
from `config.toml` (or the path in `CONFIG`) through one `tomllib` call in the venv,
and exits non-zero naming the file when it is missing.
It posts the credentials to `/auth/login` with `--data-urlencode`, so any password survives,
extracts the token with `jq -er` under `set -euo pipefail`, and prints the login response when login fails
instead of relaying a second, misleading 401.
Then it executes `curl -sS -H "Authorization: Bearer ..." "http://host:port$path"` with the remaining arguments.
No token cache, so nothing goes stale and nothing is written to disk.
`make stats` becomes `bin/curl-api /vehicle/state | jq`.

*Alternative:* a `make token` target and `TOKEN=...` in each curl.
Rejected: two steps where one wrapper does.

### Tests: the matrix without the simulator

```
tests/
  conftest.py          make_client fixture: factory(vehicle, supervise, **client_kwargs) -> client, tokens per role
  unit/test_config.py  valid file, missing file, unknown key, wrong type, empty secret, relative paths, example-secret warning
  unit/test_auth.py    token round trip, expiry via injected clock, wrong secret, hashing, role order
  unit/test_users.py   CRUD on :memory:, unique username, last-admin rule, bootstrap only when empty
  api/test_auth.py     login outcomes, /auth/me, each 401 variant
  api/test_roles.py    every endpoint x {no token, viewer, operator, admin}: status and no vehicle call on 401 / 403
  api/test_users.py    CRUD, codes, secrets hidden, demotion takes effect at once
  api/test_schema.py   security scheme, 401 / 403 declared, new paths, the full code enumeration
  sitl/conftest.py     mints an admin token before polling
```

## Risks / Trade-offs

- [Every existing caller of `/vehicle/*` breaks, and the old start flags are gone]
  → `make stats`, the README and the simulator fixture are updated in this change; the proposal marks both breaks.
- [`config.example.toml` ships a known password and secret]
  → A sim-only posture, like MediaMTX's open auth; the prod checklist lists both, and the bridge warns while the shipped secret is in use.
- [The secret sits in a file on disk]
  → The same exposure any per-machine file has; `config.toml` is gitignored, and the prod checklist covers it.
- [A per-machine file for the bridge]
  → `config.toml` is the only file to copy; the simulator stack needs none, since `compose.yaml` defaults every variable and overrides are exported for the invocation.
- [A password change does not invalidate tokens already issued]
  → Accepted for a 30-minute lifetime; a deleted user is rejected at once because the user is looked up per request.
- [`argon2-cffi` or `pyjwt` without usable type information under pyright]
  → Both ship inline types; if a diagnostic appears, a stub under `typings/` follows the pymavlink precedent.
- [`python-multipart` is needed only for the login form]
  → FastAPI checks for it when `create_app` registers the login route, not at import, and its import name is `python_multipart`;
  `uv sync` is part of the first task.

## Migration Plan

`cp config.example.toml config.toml`, edit `[link]` if the vehicle is not the simulator, `uv sync`, `make run`.
The first start creates `data/users.db` with the admin; later starts leave it alone.
To start over with a fresh admin, stop the bridge and delete `data/users.db`.
Rollback is reverting the change and deleting the database file.
