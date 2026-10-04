# Operator console for a ground robot

Oct 4, 2026 · @Michael Lutsiuk

## Summary

The project continues [uav-gc-platform](https://github.com/mluts/uav-gc-platform): the existing MAVLink bridge gains FastAPI, a WebSocket, video, gamepad control and a React console. The goal is narrow: cover the six requirements with code you can show and explain.

The repository already holds the hardest part for a newcomer to this domain: the vehicle link, telemetry, and commands with acknowledgement. You wrote it by hand, so you can defend every decision. What is missing is exactly what the six requirements ask for.

| Module | What exists | What changes |
| --- | --- | --- |
| `uav_gc/link.py` | MAVLink connection, supervisor with backoff, heartbeat watchdog | stays as is |
| `uav_gc/vehicle.py` | telemetry state, arm, disarm, mode, takeoff, goto | gains manual control (`MANUAL_CONTROL`) |
| `uav_gc/command.py` | `COMMAND_LONG` / `COMMAND_INT` with ack waiting | stays; commands go through a queue, one at a time |
| `uav_gc/api.py` | aiohttp, 4 endpoints, no auth | rewritten on FastAPI |
| `sitl/` | ArduCopter 4.7.0, quad | switched to Rover |
| tests | only `scripts/check_sitl.py` | pytest for the server; Playwright for the browser |
| frontend | none | React + TypeScript |

## Six requirements: what we build and how we prove it

Each requirement gets its own piece of code and its own proof, visible in the demo or in the tests. Anything that does not serve one of these rows is out of scope.

| Requirement | What we build | Proof |
| --- | --- | --- |
| React and TypeScript | operator console: login, video, telemetry panel, controls, user admin; `strict` TypeScript, API types generated from OpenAPI | 10 Hz telemetry does not re-render the whole tree; no `any` at the server boundary |
| WebSocket, reconnect, command queues | one WebSocket for telemetry and control; client with connection states, backoff with jitter and state recovery; command queue with id, ack and TTL | an e2e test drops the connection while driving: the rover stops, stale commands never run, state recovers |
| WebRTC or MSE/HLS | MediaMTX serves one stream two ways: WebRTC (WHEP) as primary, HLS through hls.js (MSE) as fallback | latency of both paths shown on screen; a test checks that frames decode |
| Gamepad API, low-latency input | gamepad polled in `requestAnimationFrame`, deadzone, 20 Hz setpoints over the same WebSocket, keyboard as fallback input | input-to-ack latency counter on screen; dead man's switch covered by a test |
| FastAPI: REST, WebSocket, auth, roles, OpenAPI | `api.py` on FastAPI: JWT login, roles admin / operator / viewer, user CRUD, vehicle commands, WebSocket endpoint, OpenAPI schema | role × endpoint matrix in API tests; `/docs` opens and matches the code |
| unit and e2e, Playwright | pytest for the server: unit, API and SITL integration; Playwright Test for the browser: unit for pure TS logic and e2e for the key scenarios | `make test` brings the stack up and runs both runners |

## Roles and REST API

There are three roles with different rights, and the server checks them on every endpoint and every WebSocket message. The UI only hides unavailable buttons; the decision always belongs to the server.

| Role | Watches video and telemetry | Takes control, sends commands | Manages users, revokes someone's control |
| --- | --- | --- | --- |
| viewer | yes | no | no |
| operator | yes | yes | no |
| admin | yes | yes | yes |

Only one person holds control at a time. An operator takes it explicitly, releases it, or loses it when the connection drops; an admin can revoke it.

| Method and path | Purpose | Minimum role |
| --- | --- | --- |
| `POST /auth/login` | login, issues a JWT (OAuth2 password flow) | none |
| `GET /auth/me` | current user and role | viewer |
| `GET /users`, `POST /users`, `PATCH /users/{id}`, `DELETE /users/{id}` | user management | admin |
| `GET /vehicle/state` | state snapshot (today's `/stats`) | viewer |
| `POST /vehicle/arm`, `/vehicle/disarm`, `/vehicle/mode` | discrete commands; they enter the same queue as WebSocket commands | operator |
| `GET /media/auth` | stream access check for MediaMTX | internal |
| `WS /ws` | telemetry and control | viewer |
| `GET /openapi.json`, `/docs` | API schema | none |

Implementation details:

- **Models.** Responses are Pydantic models instead of `dataclasses.asdict`, so the OpenAPI schema is exact.
- **Errors.** Today every failure returns 400. The console must tell apart "rejected by the vehicle", "timeout" and "no link", so errors get a code.
- **Users.** SQLite in a single file, passwords hashed with argon2, the first admin created from environment variables. No ORM, no migrations.
- **Lifecycle.** `link.supervise()` starts in the FastAPI `lifespan` instead of the `TaskGroup` in `__main__`.

## Key scenarios

Eight scenarios describe all system behaviour, and each becomes one e2e test. A spec that leads to none of them is unnecessary.

1. **Login and overview.** An operator logs in and sees video, telemetry and the state of both links: browser to server, and server to vehicle.
2. **Role limits.** A viewer sees the same picture, but the control buttons are disabled, and a direct attempt through the API or WebSocket returns 403.
3. **Discrete commands.** The operator takes control, arms the vehicle and changes mode. The console shows each command's path: sent, accepted, done, or rejected with a reason.
4. **Manual driving.** The operator drives the rover with a gamepad or keyboard. Position and heading change, and the screen shows input-to-ack latency.
5. **Browser link loss.** The connection drops while driving. The rover stops within 0.5 s, the console shows reconnecting, and after recovery the state is current; old setpoints and expired commands never run.
6. **Vehicle link loss.** SITL stops. The console shows "vehicle unreachable" and the age of the last telemetry; commands are rejected at once with a "no link" code.
7. **Two operators.** A second operator cannot take control while the first holds it. An admin revokes control.
8. **Video fallback.** WebRTC is unavailable, the player switches to HLS on its own and shows which path is active.

## Scope

In scope is only what the six requirements and eight scenarios need. The rest is deliberately deferred, so agents have nowhere to sprawl.

**In scope**

- one rover in SITL, one video stream, one console;
- REST, WebSocket, JWT, three roles, OpenAPI;
- WebRTC with HLS fallback;
- gamepad and keyboard;
- pytest for the server, Playwright for the browser.

**Out of scope**

- map, routes, missions, `goto` from the console;
- PWA, mobile layout, push;
- Postgres, ORM, migrations, message brokers;
- several vehicles or several cameras;
- video recording, detection, any ML;
- metrics and dashboards (Prometheus, Grafana);
- refresh tokens, SSO, action audit;
- a third test runner (Vitest, Jest, Cypress).

A MapLibre map and a PWA come first after completion: both are on the nice-to-have list. The afterthoughts in your README (jitter in the link backoff, checking the telemetry interval) fit a separate small change, but the six requirements do not depend on them.

## Targets

These numbers are starting values for specs and test thresholds. They come from reasoning about manual driving on a local network; refine them after the first measurements.

| Parameter | Value | Why |
| --- | --- | --- |
| Setpoint rate | 20 Hz | smooth control without flooding the channel |
| Setpoint lifetime | 200 ms | the server drops anything older, so the queue never "catches up" after a stall |
| Dead man's switch, step 1 | 500 ms without a fresh setpoint → neutral axes | stop on link loss or a hidden tab |
| Dead man's switch, step 2 | 2 s → HOLD mode and control released | the vehicle does not wait for an operator who is gone |
| Input-to-ack latency | p95 under 50 ms on a local network | the headline number for the demo |
| Telemetry to the console | 10 Hz | smooth heading and speed; the vehicle sends attitude at 4 Hz today, raise it |
| "Stale data" marker | age over 1 s | the operator does not trust an old picture |
| WebSocket ping | every 1 s; 3 s without a reply → connection treated as lost | detects a half-open connection |
| Reconnect backoff | 0.5 s → 8 s, factor 2, jitter ±20 % | quick return without a request storm |
| Discrete command TTL | 5 s by default | matches the ack timeouts in `vehicle.py` |
| WebRTC video latency | under 300 ms glass to glass | usable for driving |
| HLS video latency | a few seconds, show the measured value | observation only |
| Access token lifetime | 30 min | on expiry the console goes to login |

## Architecture

The Python process that already talks to the vehicle becomes the FastAPI server, and video goes around it through MediaMTX.

&#91;embedded content: architecture · browser, server, media server, simulator\]

Video never passes through Python: MediaMTX delivers it straight to the browser and only asks the server whether a viewer may watch (dashed arrow). Telemetry, commands and setpoints share one WebSocket; REST handles login, users and one-off commands.

- **One Python process.** FastAPI and the existing bridge share one asyncio event loop, so no message bus sits between them.
- **Compose services.** SITL, the server, MediaMTX and the ffmpeg test camera; in development the frontend runs on the Vite dev server.
- **Two links, shown separately.** The console reports browser-to-server and server-to-vehicle state independently; the second already exists as `link.status`.

## WebSocket protocol

One WebSocket carries telemetry down and control up, as JSON messages with a `type` field. Control splits into two classes with different guarantees, and that is the main decision of the protocol.

| Class | Examples | Guarantee | After a disconnect |
| --- | --- | --- | --- |
| Discrete command | arm, disarm, mode change | runs at most once and always gets a final status | the client resends if the TTL has not run out; the server filters duplicates by id |
| Setpoint | gamepad axes | only the newest one matters | nothing is resent, old ones are dropped |

**Messages**

| Direction | `type` | Fields | Meaning |
| --- | --- | --- | --- |
| client → server | `hello` | `token` | first message; without it the server closes the connection |
| server → client | `welcome` | `role`, `server_time`, `control` | login confirmed, `telemetry` follows right away |
| server → client | `telemetry` | full state snapshot | 10 Hz; it is state, not an event stream, so nothing needs replaying after a reconnect |
| both | `ping` / `pong` | `t`, `server_time` | liveness check, latency and clock offset measurement |
| client → server | `control.acquire` / `control.release` | none | take or release control |
| server → client | `control` | `holder`, `since` | who holds control now; sent to everyone |
| client → server | `cmd` | `id`, `name`, `args`, `ttl_ms`, `sent_at` | discrete command |
| server → client | `cmd.ack` | `id`, `status`, `reason` | `accepted` → `done`, or `rejected` / `expired` / `failed` |
| client → server | `setpoint` | `seq`, `t`, `steer`, `throttle` | axes in the range −1…1 |
| server → client | `setpoint.ack` | `seq`, `t` | echo for latency measurement |
| server → client | `error` | `code`, `message` | protocol or permission violation |

**Server rules**

- **Authorization.** The token travels in `hello`, not in the URL, so it stays out of logs. The role is checked on every `cmd`, `setpoint` and `control.*`.
- **Command queue.** Discrete commands run strictly one at a time. The reason is already in the code: `recv_ack` matches `COMMAND_ACK` by command number only, so parallel commands would mix up their acks.
- **Expiry.** A command whose TTL runs out before execution starts gets `expired` and never reaches the vehicle.
- **Duplicates.** The server remembers ids of recent commands; a resend returns the known status without running again.
- **Setpoints.** Accepted only from the control holder, with a `seq` above the previous one and an age under 200 ms. The rest are dropped silently and counted.
- **Slow client.** Each client keeps only the latest telemetry snapshot; old ones do not pile up.
- **Disconnect.** When the control holder's connection goes away, the dead man's switch fires and control is released.

**Client rules**

- **Connection states.** `connecting` → `authenticating` → `online` → `reconnecting`; the console shows the current one.
- **Reconnect.** Backoff with jitter; after `welcome` the client resends unfinished commands with a live TTL, and asks for control again only on an explicit operator action.
- **Hidden tab.** `requestAnimationFrame` pauses, setpoints stop, and the server stops the rover. This is the desired behaviour, and the console must show it to the operator.

**Types.** Messages are Pydantic models discriminated by `type`. They produce a JSON Schema, and that produces TypeScript types, so REST and WebSocket share one source of truth.

## Stack and key decisions

The stack is minimal: every row is either already in the repository or named in the six requirements.

| Layer | Choice | Why |
| --- | --- | --- |
| Vehicle bridge | existing asyncio + pymavlink code | works, written by you |
| API | FastAPI, Pydantic v2, uvicorn | one of the six requirements; OpenAPI out of the box |
| Auth | JWT (PyJWT), argon2, SQLite | shortest path to real roles |
| Frontend | React, TypeScript `strict`, Vite | one of the six requirements |
| API types | generated from OpenAPI and JSON Schema | the compiler checks the contract |
| Video | MediaMTX; WebRTC through WHEP, HLS through hls.js | one server covers both paths from the requirement |
| Input | Gamepad API + keyboard | see below |
| Tests | pytest (server), Playwright Test (browser) | one runner per side; Playwright is named in the requirements |
| Run | Docker Compose + the existing Makefile | SITL already runs in Docker |

**Low-latency input: the Gamepad API over the existing WebSocket.** It is the most accessible option, and the requirements name it. It works in every browser without permissions, picks up any USB gamepad or a radio transmitter in joystick mode, and needs nothing new on the server.

- **Polling.** `navigator.getGamepads()` inside `requestAnimationFrame`, with deadzone and response curve in a pure function.
- **Sending.** A separate 20 Hz timer takes the latest axis values instead of sending every frame. The rate does not depend on the monitor.
- **Keyboard.** WASD produces the same axes through the same input interface, so the demo works without hardware and tests do not depend on a gamepad.
- **Vehicle side.** The server turns a setpoint into MAVLink `MANUAL_CONTROL` in MANUAL mode.

Rejected options: a WebRTC DataChannel gives lower latency under packet loss but needs a WebRTC stack on the server (aiortc); WebTransport needs HTTP/3; WebHID works only in Chromium and adds nothing. The weak spot of WebSocket is that one lost packet delays the whole queue. TTL and the "only the newest matters" rule cover it, and that is a good story for the demo.

**State in React.** Telemetry lives outside the component tree in its own store, and components subscribe to single fields through `useSyncExternalStore`. Connection, queue and input logic are plain TypeScript modules without React, so they can be tested without a browser.

## Simulators and real hardware

The whole demo runs on one laptop without hardware, and a real device plugs in where the simulator was, over the same protocol.

| Channel | Simulator | Real hardware |
| --- | --- | --- |
| Vehicle | ArduPilot Rover SITL in Docker (the existing image, built as rover instead of copter) | any autopilot speaking MAVLink over serial or UDP; `link.py` already supports it |
| Video | ffmpeg publishes a test picture with a clock in the frame to MediaMTX over RTSP | a phone publishes its camera through WHIP from the browser |
| Input | keyboard; in tests a replaced `navigator.getGamepads` | a USB gamepad or a radio transmitter in joystick mode |
| Browser link loss | in tests Playwright intercepts the WebSocket and closes it | switch off Wi-Fi on the laptop |
| Vehicle link loss | `docker kill` on the SITL container (the `make kill` target exists) | unplug the telemetry cable |

The clock in the test video exists to measure latency: the difference between it and the clock on the page gives glass-to-glass latency with no extra tooling.

Rover replaces Copter for two reasons. The target platform is a ground vehicle, and stopping a ground vehicle on link loss is safe and obvious, unlike a drone in the air. The change is small: another build target in `sitl/Dockerfile` and another vehicle type in `entrypoint.sh`; `arm`, `disarm` and `set_mode` in `vehicle.py` work unchanged, because mode names come from the heartbeat.

## Capabilities for openspec

Eleven capabilities, each sized for one change by one agent and a 20–30 minute review. The first seven live on the server, the other four in the frontend.

| Capability | What it describes | Depends on | Requirement |
| --- | --- | --- | --- |
| `rover-sitl` | SITL as Rover, Compose for the bridge and the simulator | none | foundation |
| `http-api` | FastAPI instead of aiohttp, Pydantic state models, error codes, OpenAPI | none | FastAPI |
| `auth-and-roles` | users in SQLite, login, JWT, three roles, user CRUD | `http-api` | FastAPI |
| `telemetry-stream` | `WS /ws`: `hello`, `welcome`, 10 Hz snapshots, ping/pong, slow clients | `auth-and-roles` | WebSocket |
| `command-queue` | discrete commands: id, statuses, TTL, duplicates, one at a time | `telemetry-stream` | WebSocket |
| `manual-control` | control ownership, setpoints, dropping stale ones, dead man's switch, `MANUAL_CONTROL` | `command-queue` | Gamepad |
| `video-gateway` | MediaMTX, test camera, stream access check | `auth-and-roles` | WebRTC / HLS |
| `operator-console` | React app: login, console layout, telemetry panel, indicators for both links, admin page | `telemetry-stream` | React |
| `ws-client` | connection client: states, backoff, reconnect, client-side command queue | `command-queue` | WebSocket |
| `operator-input` | gamepad, keyboard, deadzone, 20 Hz, latency indicator | `manual-control`, `ws-client` | Gamepad |
| `video-player` | WHEP player, switch to HLS, latency display | `video-gateway` | WebRTC / HLS |

Test infrastructure is not a separate capability: every change brings its own tests, and shared fixtures appear in the first change that needs them.

## Order of changes

Eight changes, each ending with something you can run and show. After the fourth there is a console with live telemetry, enough for a first demo.

1. **`rover-compose`**: capability `rover-sitl`. Result: `make up` starts Rover SITL and the bridge, `/stats` shows ground modes.
2. **`fastapi-api`**: `http-api` plus the first pytest unit and API tests. Result: the same API on FastAPI, `/docs` works, tests check state and commands against SITL.
3. **`auth-roles`**: `auth-and-roles`. Result: login and the role × endpoint matrix in tests.
4. **`live-telemetry`**: `telemetry-stream`, `operator-console`, and the connect and reconnect part of `ws-client`. Result: a console with live telemetry; scenarios 1 and 6.
5. **`commands`**: `command-queue` and the client-side queue of `ws-client`. Result: arm and mode change from the console; scenarios 2 and 3.
6. **`video`**: `video-gateway`, `video-player`. Result: video in the console over both paths; scenario 8.
7. **`manual-drive`**: `manual-control`, `operator-input`. Result: the rover drives from a gamepad and stops on link loss; scenarios 4, 5 and 7.
8. **`demo`**: README with measured latencies, a short screen recording, a description of how changes were sliced and reviewed with agents.

Changes 2 and 3 are server-only and closest to your experience, so use them to settle the openspec process. Change 6 does not depend on 5 and can go to a separate agent in parallel.

## Testing: pytest for the server, Playwright for the browser

Two runners, split by where the code runs: pytest owns everything in Python, Playwright Test owns everything in the browser. `make test` runs both.

| Suite | Runner | What it checks | Needs |
| --- | --- | --- | --- |
| Server unit | pytest, pytest-asyncio | command queue (TTL, duplicates, one at a time), setpoint filtering, dead man's switch timing, control ownership, role checks, message models | nothing: a fake vehicle and an injected clock |
| Server API | pytest with FastAPI's test client | REST and `/ws` contract: login, role × endpoint matrix, user CRUD, error codes, `hello` / `welcome`, command statuses | fake vehicle, no SITL |
| Server integration | pytest, marked `sitl` | the bridge against real ArduPilot: arm, mode change, `MANUAL_CONTROL` moves the rover, link loss and recovery | SITL container |
| Frontend unit | Playwright Test, no `page` | pure TS logic: client command queue, backoff, connection states, deadzone and axis mapping, message parsing | Node only |
| End to end | Playwright Test, Chromium | the eight key scenarios | full stack: SITL, server, MediaMTX, test camera |

**Server side**

- **Seam for fakes.** The queue, control ownership and the dead man's switch depend on a small interface that `Vehicle` satisfies: arm, disarm, set mode, manual control, state, link status. A fake records calls and can reject or time out on demand.
- **Injected clock.** TTL and dead man's switch logic take time from a passed-in function, so tests advance it instead of sleeping.
- **SITL fixture.** A session fixture starts the container and waits until the vehicle is `armable`; `SITL_SPEEDUP` already exists in the image. `scripts/check_sitl.py` becomes the first `sitl` test.
- **Role fixtures.** Ready tokens for admin, operator and viewer.

**Browser side**

- **Stack.** `globalSetup` brings Compose up once for the whole e2e run.
- **Roles.** Ready admin, operator and viewer sessions through `storageState`, so tests do not log in each time.
- **Gamepad.** `page.addInitScript` replaces `navigator.getGamepads` with an object whose axes the test changes through `page.evaluate`.
- **Connection loss.** `page.routeWebSocket` passes traffic to the real server and closes the connection when the test says so.
- **Time.** `page.clock` fast-forwards timers, so backoff is checked without real waiting.
- **Video.** The test waits until `<video>` reports a non-zero frame width and the decoded-frame counter starts growing.

Frontend unit tests run on the Playwright Test runner without a browser, so the browser side keeps a single runner. Most behaviour is pinned down in the fast suites; e2e covers only the eight scenarios, where the pieces meet.

**Rule for agents.** A change is not done without tests at the level it touches. `make test-fast` runs the suites that need no Docker and is the loop while working; `make test` must pass from a clean clone before review.

## Open questions

Settle the first two before writing the related specs, because they change decisions. The rest are short checks at the start of their change.

- [ ] **Rover or Copter.** The doc assumes Rover. If you keep Copter, the dead man's switch changes (hover instead of stop), and so does the axis mapping.
- [ ] **Video codec in tests.** The Chromium that Playwright installs usually lacks H.264. Options: a VP8 test camera, or running e2e in real Chrome (`channel: 'chrome'`). Check with a short spike before the `video` change.
- [ ] **`MANUAL_CONTROL` axes for Rover.** Which fields and ranges map to steering and throttle in the chosen ArduPilot version; the alternative is `RC_CHANNELS_OVERRIDE`.
- [ ] **Rover version for SITL.** Which stable tag replaces `Copter-4.7.0`.
- [ ] **Token for video.** How MediaMTX in your version passes the token from the WHEP request to the access check.
- [ ] **Repository name.** `uav-gc-platform` reads oddly for a ground vehicle; rename it, or keep it with a note in the README.
- [ ] **Frontend unit runner.** The doc assumes Playwright Test without a browser, so the browser side has one runner; Vitest is the common alternative. React component tests are optional either way.

## Five-minute demo

This run shows all six requirements in a row, and it is worth recording for the README.

1. `make up`, open the console, log in as operator. Video, telemetry and both links show as up.
2. Open a second window as viewer: the same picture, control buttons disabled.
3. Take control, press arm, switch to MANUAL. Each command walks through its statuses on screen.
4. Drive with the gamepad. Heading and position change, the indicator shows input-to-ack latency.
5. Cut the network while driving. The rover stops, the console reconnects, and control has to be taken again.
6. Stop SITL. The console shows "vehicle unreachable" and the telemetry age.
7. Switch video to HLS and compare its latency with WebRTC.
8. Open `/docs` and run `make test`, which runs pytest and then Playwright.
