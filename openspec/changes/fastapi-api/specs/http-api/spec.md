# Spec Delta

## Purpose

Exposes the vehicle bridge over HTTP: a typed state document, arm / disarm / mode commands, error codes a client can branch on, and an OpenAPI description generated from the same models, so clients can be written and type-checked against the schema.

## ADDED Requirements

### Requirement: Vehicle state document
`GET /vehicle/state` SHALL return the current vehicle state as one JSON document
with the fields `position`, `attitude`, `batteries`, `mode`, `armed`, `armable`, `position_ok`,
`link`, `ts` and `protocol_version`.
Each telemetry group SHALL carry `age_s`, the seconds since its last message.
`link` SHALL carry `status` (`CONNECTING`, `UP` or `DOWN`), `last_error` and `heartbeat_age_s`.
The endpoint SHALL answer with status 200 whenever the server is running, whatever the state of the vehicle link.

#### Scenario: State with live telemetry
- **WHEN** the vehicle link is `UP` and telemetry is flowing, and `GET /vehicle/state` is requested
- **THEN** the response is 200 with `position`, `attitude` and at least one battery present, `mode` and `armed` set, and every `age_s` under 2 seconds

#### Scenario: State before any telemetry
- **WHEN** the vehicle has never been reachable and `GET /vehicle/state` is requested
- **THEN** the response is 200 with `position`, `attitude`, `mode` and `armed` null, `batteries` empty, and `link.status` not `UP`

#### Scenario: Ages grow when telemetry stops
- **WHEN** the vehicle link goes down and `GET /vehicle/state` is requested twice, 2 seconds apart
- **THEN** both responses keep the last known values, and every `age_s` in the second is about 2 seconds greater than in the first

### Requirement: Vehicle commands
`POST /vehicle/arm`, `POST /vehicle/disarm` and `POST /vehicle/mode` SHALL send the command to the vehicle
and SHALL answer with success only after the vehicle's own reported state shows the change.
`POST /vehicle/mode` SHALL take the mode name in a JSON body as `mode`, compared without regard to case.

#### Scenario: Arm
- **WHEN** the vehicle is armable and `POST /vehicle/arm` is requested
- **THEN** the response is 200 with `{"armed": true}`, and `GET /vehicle/state` reports `armed` as true

#### Scenario: Disarm
- **WHEN** the vehicle is armed and `POST /vehicle/disarm` is requested
- **THEN** the response is 200 with `{"armed": false}`, and `GET /vehicle/state` reports `armed` as false

#### Scenario: Mode change
- **WHEN** `POST /vehicle/mode` is requested with body `{"mode": "hold"}`
- **THEN** the response is 200 with `{"mode": "HOLD"}`, and `GET /vehicle/state` reports `mode` as `HOLD`

### Requirement: Failures carry a machine-readable code
Every failed request to a vehicle endpoint SHALL answer with a JSON body holding `code` and `message`,
where `code` is one of the values below and the HTTP status is the one listed for it.

| `code` | Status | Meaning |
| --- | --- | --- |
| `rejected` | 409 | the vehicle answered the command and refused it |
| `timeout` | 504 | the vehicle did not answer, or accepted the command but never reported the change |
| `no_link` | 503 | the vehicle link is not up, went down while the command was waiting, or the vehicle has not been identified yet |
| `unknown_mode` | 422 | the requested mode is not one the vehicle has |
| `invalid_request` | 422 | the request body is missing or malformed |
| `internal` | 500 | an unexpected failure in the server |

#### Scenario: Vehicle refuses a command
- **WHEN** `POST /vehicle/arm` is requested and the vehicle acknowledges with a refusal
- **THEN** the response is 409 with `code` `rejected`, and `message` names the vehicle's result

#### Scenario: Vehicle does not answer
- **WHEN** `POST /vehicle/arm` is requested and the vehicle sends no acknowledgement
- **THEN** within 10 seconds the response is 504 with `code` `timeout`

#### Scenario: Change accepted but never reported
- **WHEN** `POST /vehicle/mode` is requested, the vehicle accepts it, and its reported mode does not change
- **THEN** within 15 seconds the response is 504 with `code` `timeout`

#### Scenario: Command while the link is down
- **WHEN** the vehicle link is not `UP` and `POST /vehicle/arm`, `/vehicle/disarm` or `/vehicle/mode` is requested
- **THEN** within 1 second the response is 503 with `code` `no_link`, and nothing is sent to the vehicle

#### Scenario: Link drops while a command is waiting
- **WHEN** a command is waiting for the vehicle and the link goes down
- **THEN** the response is 503 with `code` `no_link`

#### Scenario: Unknown mode
- **WHEN** `POST /vehicle/mode` is requested with body `{"mode": "land"}` against a rover
- **THEN** the response is 422 with `code` `unknown_mode`, `message` names the mode, and the vehicle's mode is unchanged

#### Scenario: Malformed request
- **WHEN** `POST /vehicle/mode` is requested with no body or without `mode`
- **THEN** the response is 422 with `code` `invalid_request`

#### Scenario: Unexpected failure
- **WHEN** handling a request raises an error the server does not classify
- **THEN** the response is 500 with `code` `internal`, and the body holds no stack trace

### Requirement: OpenAPI schema describes the API
The server SHALL publish its schema at `GET /openapi.json` and interactive documentation at `GET /docs`,
both generated from the models the endpoints use, so the schema cannot drift from the behaviour.

#### Scenario: Schema lists every endpoint
- **WHEN** `GET /openapi.json` is requested
- **THEN** it lists `/vehicle/state`, `/vehicle/arm`, `/vehicle/disarm` and `/vehicle/mode` with their methods

#### Scenario: State is fully typed
- **WHEN** the schema of the `GET /vehicle/state` response is read
- **THEN** every field has a declared type, nullable where it can be null, and `link.status` is an enumeration of `CONNECTING`, `UP` and `DOWN`

#### Scenario: Errors are documented
- **WHEN** the schema of a command endpoint is read
- **THEN** it declares the 409, 422, 503 and 504 responses with the error body, and `code` is an enumeration of the defined values

#### Scenario: Documentation page opens
- **WHEN** `GET /docs` is requested in a browser
- **THEN** the page loads and lists the vehicle endpoints

### Requirement: Old paths are not served
The server SHALL NOT answer on the paths used before this capability: `/stats`, `/arm`, `/disarm` and `/mode`.

#### Scenario: Old state path
- **WHEN** `GET /stats` is requested
- **THEN** the response is 404

#### Scenario: Old command paths
- **WHEN** `POST /arm`, `POST /disarm` or `POST /mode?newmode=hold` is requested
- **THEN** the response is 404 and nothing is sent to the vehicle
