# Spec Delta

## Purpose

Identifies who is calling the API and what they may do:
a login that issues a bearer token, three ordered roles with a minimum role per endpoint,
user management for administrators, a first administrator from the configuration file,
and error codes a client can branch on when a request is unauthenticated or forbidden.

## ADDED Requirements

### Requirement: Login issues a bearer token
`POST /auth/login` SHALL accept the OAuth2 password form, form-encoded `username` and `password`,
and SHALL answer 200 with `access_token` and `token_type` `bearer`
when the credentials match a user.
The token SHALL be valid for 30 minutes unless configured otherwise.
A wrong username or a wrong password SHALL both answer 401 with code `invalid_credentials`
and the same message, so a caller cannot learn which was wrong.

#### Scenario: Successful login
- **WHEN** `POST /auth/login` is requested with the username and password of an existing user
- **THEN** the response is 200 with a non-empty `access_token` and `token_type` `bearer`

#### Scenario: Wrong password
- **WHEN** `POST /auth/login` is requested with an existing username and a wrong password
- **THEN** the response is 401 with code `invalid_credentials`

#### Scenario: Unknown username
- **WHEN** `POST /auth/login` is requested with a username that does not exist
- **THEN** the response is 401 with code `invalid_credentials` and the same body as for a wrong password

#### Scenario: Missing form fields
- **WHEN** `POST /auth/login` is requested without `username` or without `password`
- **THEN** the response is 422 with code `invalid_request`

### Requirement: Requests carry a bearer token
Every endpoint except `POST /auth/login`, `GET /openapi.json`, `GET /docs` and
`GET /docs/oauth2-redirect` SHALL require an `Authorization: Bearer <token>` header.
The server SHALL NOT serve `/redoc`. `GET /auth/me` SHALL return the caller's `id`,
`username` and `role`. A missing, malformed, expired or forged token, or a token for a
user that no longer exists, SHALL answer 401 with code `unauthenticated` and a
`WWW-Authenticate: Bearer` header, with no other effect.

#### Scenario: Current user
- **WHEN** `GET /auth/me` is requested with a valid token
- **THEN** the response is 200 with the `id`, `username` and `role` of the user the token was issued to

#### Scenario: No token
- **WHEN** `GET /auth/me` is requested without an `Authorization` header
- **THEN** the response is 401 with code `unauthenticated` and a `WWW-Authenticate` header

#### Scenario: Expired token
- **WHEN** `GET /auth/me` is requested with a token issued 31 minutes earlier under the default lifetime
- **THEN** the response is 401 with code `unauthenticated`

#### Scenario: Forged token
- **WHEN** `GET /auth/me` is requested with a token signed with a different secret
- **THEN** the response is 401 with code `unauthenticated`

#### Scenario: Token of a deleted user
- **WHEN** a user is deleted and `GET /auth/me` is requested with a token issued to them before the deletion
- **THEN** the response is 401 with code `unauthenticated`

#### Scenario: ReDoc is not served
- **WHEN** `GET /redoc` is requested
- **THEN** the response is 404

### Requirement: Roles are ordered and checked by the server
There SHALL be three roles — `viewer`, `operator` and `admin` — each including the rights
of the one before. A request whose token carries a role below an endpoint's minimum SHALL
answer 403 with code `forbidden` and SHALL have no other effect.

#### Scenario: Viewer cannot command
- **WHEN** `POST /vehicle/arm` is requested with a `viewer` token
- **THEN** the response is 403 with code `forbidden`, and nothing is sent to the vehicle

#### Scenario: Operator cannot manage users
- **WHEN** `GET /users` is requested with an `operator` token
- **THEN** the response is 403 with code `forbidden`

#### Scenario: Admin may do everything
- **WHEN** `GET /vehicle/state`, `POST /vehicle/mode` and `GET /users` are requested with an `admin` token
- **THEN** none of the responses is 401 or 403

#### Scenario: Demotion takes effect at once
- **WHEN** an operator holds a valid token, an admin changes that user's role to `viewer`, and the operator requests `POST /vehicle/arm` with the same token
- **THEN** the response is 403 with code `forbidden`

### Requirement: Each endpoint declares a minimum role
Every endpoint SHALL declare the minimum role listed below.

| Method and path | Minimum role |
| --- | --- |
| `POST /auth/login`, `GET /openapi.json`, `GET /docs` | none |
| `GET /auth/me` | `viewer` |
| `GET /vehicle/state` | `viewer` |
| `POST /vehicle/arm`, `POST /vehicle/disarm`, `POST /vehicle/mode` | `operator` |
| `GET /users`, `POST /users`, `PATCH /users/{id}`, `DELETE /users/{id}` | `admin` |

#### Scenario: OpenAPI declares the roles
- **WHEN** the OpenAPI schema is read
- **THEN** each endpoint's minimum role matches the table above

### Requirement: Administrators manage users
`GET /users` SHALL list every user as `id`, `username` and `role`; `POST /users` SHALL take
`username`, `password` and `role` and answer 201; `PATCH /users/{id}` SHALL take any of
`password` and `role` and answer 200; `DELETE /users/{id}` SHALL answer 204. No response SHALL
contain a password or a hash. A duplicate username answers 409 `username_taken`; an unknown
`id` answers 404 `not_found`; a role outside the three answers 422 `invalid_request`.

#### Scenario: Create a user who can then log in
- **WHEN** an admin requests `POST /users` with a new username, a password and role `operator`
- **THEN** the response is 201 with `id`, `username` and `role` `operator`, and a login with those credentials succeeds

#### Scenario: Listing hides secrets
- **WHEN** an admin requests `GET /users`
- **THEN** every entry has exactly `id`, `username` and `role`

#### Scenario: Duplicate username
- **WHEN** an admin requests `POST /users` with a username that already exists
- **THEN** the response is 409 with code `username_taken`

#### Scenario: Unknown user
- **WHEN** an admin requests `PATCH /users/{id}` or `DELETE /users/{id}` with an id no user has
- **THEN** the response is 404 with code `not_found`

#### Scenario: Password change
- **WHEN** an admin requests `PATCH /users/{id}` with a new `password`
- **THEN** a login with the old password answers 401 and a login with the new one answers 200

#### Scenario: Invalid role
- **WHEN** an admin requests `POST /users` with role `pilot`
- **THEN** the response is 422 with code `invalid_request`

### Requirement: The last administrator cannot be removed
A request that would delete the only remaining `admin`, or change their role to something else,
SHALL answer 409 with code `last_admin` and SHALL leave the user unchanged.

#### Scenario: Deleting the only admin
- **WHEN** exactly one admin exists and `DELETE /users/{id}` is requested for them
- **THEN** the response is 409 with code `last_admin` and the admin still exists

#### Scenario: Demoting the only admin
- **WHEN** exactly one admin exists and `PATCH /users/{id}` is requested for them with role `operator`
- **THEN** the response is 409 with code `last_admin` and their role is still `admin`

#### Scenario: Removing one of two admins
- **WHEN** two admins exist and `DELETE /users/{id}` is requested for one of them
- **THEN** the response is 204

### Requirement: The first administrator comes from the configuration file
When the server starts with no users it SHALL create one `admin` from `users.admin_username`
and `users.admin_password`; with either key missing it SHALL exit non-zero naming both keys.
A missing or empty `auth.secret` SHALL exit non-zero naming `auth.secret` (a missing `[auth]`
section names `auth`). The shipped example `auth.secret` SHALL start and log a warning naming
`auth.secret`. With users present it SHALL ignore `users.admin_username` and `users.admin_password`.

#### Scenario: First start
- **WHEN** the server starts with an empty user store and both admin keys present
- **THEN** a login with those credentials succeeds and `GET /auth/me` reports role `admin`

#### Scenario: Empty store without credentials
- **WHEN** the server starts with an empty user store and `users.admin_password` missing
- **THEN** it exits non-zero and the message names `users.admin_username` and `users.admin_password`

#### Scenario: Missing secret
- **WHEN** the server starts with an `[auth]` section whose `secret` is missing or empty
- **THEN** it exits non-zero and the message names `auth.secret`

#### Scenario: Example secret in use
- **WHEN** the server starts with `auth.secret` equal to the value shipped in `config.example.toml`
- **THEN** it starts, and a warning naming `auth.secret` is logged

#### Scenario: Existing users are left alone
- **WHEN** the server starts with users present and `users.admin_password` changed to a new value
- **THEN** a login with the stored password succeeds and one with the new value fails

### Requirement: The development loop works with a token
`bin/curl-api <path> [curl options]` SHALL read the listen address and the admin credentials from `config.toml`,
SHALL log in, and SHALL send the request with the bearer token.
When `config.toml` is missing it SHALL exit non-zero naming the file;
when the login fails it SHALL print the login response and exit non-zero.
`make stats` SHALL print the state document through it.

#### Scenario: State through the wrapper
- **WHEN** the bridge is running and `make stats` is run with `config.toml` holding the admin credentials
- **THEN** the state document is printed

#### Scenario: Command through the wrapper
- **WHEN** `bin/curl-api /vehicle/mode -XPOST -H 'Content-Type: application/json' -d '{"mode": "hold"}'` is run
- **THEN** the response is the mode response, not a 401

#### Scenario: Wrapper without a configuration file
- **WHEN** `bin/curl-api /vehicle/state` is run with no `config.toml` present
- **THEN** it exits non-zero and the message names `config.toml`

#### Scenario: Wrapper with a wrong password
- **WHEN** `bin/curl-api /vehicle/state` is run with `config.toml` holding a password the bridge does not accept
- **THEN** it prints the login response with code `invalid_credentials` and exits non-zero
