# Tasks

## 1. Dependencies and configuration

- [ ] 1.1 Add `pyjwt`, `argon2-cffi` and `python-multipart` to `pyproject.toml`, run `uv sync` and commit `uv.lock`;
  verify `python -c "import jwt, argon2, python_multipart"` runs in the venv and `make typecheck` passes
- [ ] 1.2 Add `uav_gc/config.py`: the Pydantic `Config` with sections `http`, `link`, `log`, `auth` and `users`,
  the defaults from the design, `extra="forbid"`, a non-empty `secret`, `load_config(path)` on `tomllib`
  resolving relative paths against the file's directory, and the named example-secret constant with its warning;
  add `config.example.toml` with development values and comments, and `config.toml` and `data/` to `.gitignore`;
  verify with `tests/unit/test_config.py`: a valid file, the defaults, a missing file naming the path,
  an unknown key, a wrong type, an empty secret, a relative `database` resolved next to the file,
  and the warning captured with `caplog`
- [ ] 1.3 Default `LAN_IP` to `127.0.0.1` in `compose.yaml` and reword the `.env.example` header to say the file is optional;
  verify that with no `.env` present `make up` starts all three services and `bin/curl-mediamtx-api` answers

## 2. Models, errors and auth primitives

- [ ] 2.1 Add `Role`, `User`, `UserCreate`, `UserUpdate` and `Token` to `uav_gc/models.py`
  with the six new error codes, and restructure `uav_gc/errors.py` around an `ApiError` base
  with `CommandError`, `AuthError` and `UserError` under it, one subclass per code;
  verify the existing unit and API tests still pass and `make typecheck` passes
- [ ] 2.2 Add `uav_gc/auth.py`: the role rank table, `hash_password(hasher, password)` / `verify_password(hasher, hash, password)`
  with the dummy-hash path for unknown users, and `TokenCodec(secret, ttl_s, now)` that issues and decodes tokens;
  verify with `tests/unit/test_auth.py`, using the `CHEAPEST` argon2 profile: round trip, expiry through an injected clock,
  a token signed with another secret, a tampered token, hash verify success and failure, role ordering

## 3. User store

- [ ] 3.1 Add `uav_gc/users.py` with `UserStore(path)`: table creation on open, parent directory creation,
  the lock, and `count`, `list`, `get`, `get_by_username`, `create`, `update`, `delete`
  taking password hashes, never passwords, and raising `UsernameTaken` and `NotFound`;
  verify with `tests/unit/test_users.py` on `:memory:` covering each method and both errors
- [ ] 3.2 Add the last-admin rule inside the lock for `delete` and `update`,
  and `bootstrap(username, password_hash)` that acts only on an empty store;
  verify with unit tests that deleting or demoting the only admin raises `LastAdmin`,
  that one of two admins can be deleted,
  and that a second bootstrap with another hash leaves one user carrying the first hash

## 4. API routes and role checks

- [ ] 4.1 Extend `create_app` to `(vehicle, supervise=None, *, users, auth)` with `Auth(users, codec, hasher)` as a plain holder,
  replace the command handler with one `ApiError` handler over the extended status table
  that adds `WWW-Authenticate: Bearer` on 401,
  and add the `make_client` fixture to `tests/conftest.py`, a factory taking `vehicle`, `supervise` and `TestClient` options,
  building `Auth` with the `CHEAPEST` argon2 profile and returning a client and a token per role;
  migrate the existing API tests to the fixture and verify they still pass with no role enforced yet
- [ ] 4.2 Add `authenticate(token)`, `authorize(user, role)` and `require(role)` to `Auth`,
  reading the token through an `OAuth2PasswordBearer` instance with `auto_error=False`,
  put `viewer` on the state route and `operator` on the command routes,
  and make the simulator fixture build the in-memory store with one admin, mint a token through the codec,
  and set the client's default `Authorization` header before polling;
  verify with unit tests that `authenticate` raises `Unauthenticated` for a bad, an expired and a deleted user's token
  and that `authorize` raises `Forbidden` below the required rank,
  with `tests/api/test_roles.py` for the vehicle routes:
  no token answers 401, `viewer` on a command answers 403 with no vehicle call, `operator` and `admin` answer neither,
  and that `make test` passes with no bridge connected
- [ ] 4.3 Add `POST /auth/login` on `OAuth2PasswordRequestForm` returning `Token`, and `GET /auth/me`;
  verify with `tests/api/test_auth.py`: success, wrong password, unknown username with the same body,
  missing fields answering 422 `invalid_request`, `/auth/me` fields,
  and 401 `unauthenticated` for an expired, a forged and a deleted user's token
- [ ] 4.4 Add `GET /users`, `POST /users` (201), `PATCH /users/{id}` and `DELETE /users/{id}` (204), all `admin`;
  verify with `tests/api/test_users.py`: create then log in, listing shows only `id`, `username`, `role`,
  duplicate 409 `username_taken`, unknown id 404 `not_found`, password change, invalid role 422,
  the two `last_admin` cases, deleting one of two admins, and a demotion taking effect on the next request;
  extend the matrix in `tests/api/test_roles.py` with the auth and user routes
- [ ] 4.5 Declare the 401 and 403 responses on every protected route and build the app with `redoc_url=None`;
  verify with `tests/api/test_schema.py`: the eight paths, an OAuth2 password scheme with token URL `/auth/login`
  referenced by the state route and not by login, the command routes declaring 401, 403, 409, 422, 503 and 504,
  `ErrorCode` enumerating all twelve codes, `/docs` answering 200 and `/redoc` answering 404

## 5. Entry point and development loop

- [ ] 5.1 Rewrite `uav_gc/__main__.py`: `--config` defaulting to `config.toml`, `load_config`, logging at `log.level`,
  the store at `users.database`, bootstrap on an empty store or exit naming `users.admin_username` and `users.admin_password`,
  `TokenCodec` from `[auth]` and `Auth` with the default `PasswordHasher()`, `MavLink(device, baud)` from `[link]`, `create_app`, and uvicorn on `[http]`;
  delete `MavLink.from_args` and its argparse import; replace `run-tcp` and `run-udp` with `make run` in the `Makefile`;
  verify `make run` with no `config.toml` exits naming the path, with an unknown key exits naming the key,
  and with the example file starts, logs the secret warning, creates `data/users.db`, and serves `/docs`
- [ ] 5.2 Add `bin/curl-api` and point `make stats` at it;
  verify against the running bridge that `make stats` prints the state document,
  that the wrapper's `POST /vehicle/mode` with `{"mode": "hold"}` answers `{"mode": "HOLD"}`,
  that a bare `curl 127.0.0.1:8080/vehicle/state` answers 401,
  that with no `config.toml` the wrapper exits non-zero naming the file,
  and that with a wrong password it prints the login response and exits non-zero
- [ ] 5.3 Update `README.md`: the quickstart with `cp config.example.toml config.toml` and `make run`,
  a login section, the roles table, the curl examples through `bin/curl-api`, the new rows of the error table,
  and how to reset the user database;
  add the secret and admin password rows to `docs/prod-checklist.md`;
  verify every README example runs as written

## 6. Integration

- [ ] 6.1 Verify from a clean clone with no `.env`: `uv sync`, `make build`, `cp config.example.toml config.toml`, `make test` passes;
  run `openspec validate auth-roles --strict` and verify it passes
