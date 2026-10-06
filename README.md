# uav-gc-platform

Ground-control platform.

MAVLink telemetry bridge + vehicle command API.

Tested against ArduPilot Rover SITL in Docker.

## Prerequisites

- Docker
- GNU make
- uv (installs Python 3.13)
- curl + jq

The first `make build` clones and compiles ArduPilot; it takes many minutes.

## Quickstart

```
uv sync          # installs Python deps into .venv
make build       # builds the Rover SITL image (first build is slow)
make up          # starts the simulator + video stack in the background
make run-tcp     # runs the bridge on http://127.0.0.1:8080 against the simulator
```

`make up` starts the ArduRover simulator, MediaMTX and the virtual camera.
The bridge runs on the host and connects to the simulator's TCP port
(`127.0.0.1:5762`); it reconnects on its own if the simulator restarts.

## HTTP API

Interactive documentation is at <http://127.0.0.1:8080/docs>; the raw OpenAPI
schema is at `/openapi.json`.

```
curl '127.0.0.1:8080/vehicle/state'
curl -XPOST '127.0.0.1:8080/vehicle/arm'
curl -XPOST '127.0.0.1:8080/vehicle/disarm'
curl -XPOST '127.0.0.1:8080/vehicle/mode' -H 'Content-Type: application/json' -d '{"mode": "hold"}'
curl -XPOST '127.0.0.1:8080/vehicle/mode' -H 'Content-Type: application/json' -d '{"mode": "manual"}'
```

Rover modes: `hold`, `manual`, `guided`, ... `land` is a Copter mode and is
rejected with an `unknown_mode` error.

Failed requests answer `{"code": ..., "message": ...}`:

| `code` | Status | Meaning |
| --- | --- | --- |
| `rejected` | 409 | the vehicle answered the command and refused it |
| `timeout` | 504 | the vehicle did not answer, or accepted the command but never reported the change |
| `no_link` | 503 | the vehicle link is not up, went down while the command was waiting, or the vehicle has not been identified yet |
| `unknown_mode` | 422 | the requested mode is not one the vehicle has |
| `invalid_request` | 422 | the request body is missing or malformed |
| `internal` | 500 | an unexpected failure in the server |

Example

```
make stats

curl 127.0.0.1:8080/vehicle/state | jq
{
  "position": {
    "lat": -35.3632611,
    "lon": 149.16523,
    "alt_msl": 583.96,
    "alt_rel": -0.036,
    "vn": -0.01,
    "ve": 0.01,
    "vd": 0.0,
    "heading": 354.93,
    "age_s": 0.37
  },
  "attitude": {
    "roll": 0.0011724279029294848,
    "pitch": 0.0009718998335301876,
    "yaw": -0.08861448615789413,
    "age_s": 0.37
  },
  "batteries": [
    {
      "id": 0,
      "voltage": 12.6,
      "current": 0.0,
      "remaining_pct": 100,
      "temperature": null,
      "charge_state": "MAV_BATTERY_CHARGE_STATE_OK",
      "faults": 0,
      "age_s": 0.37
    }
  ],
  "mode": "MANUAL",
  "armed": false,
  "armable": true,
  "position_ok": true,
  "link": {
    "status": "UP",
    "last_error": null,
    "heartbeat_age_s": 0.37
  },
  "ts": 1791148785.0612469,
  "protocol_version": "2.0"
}
```

## Link loss and recovery

The bridge reconnects on its own; no restart needed.

```
make kill      # stop the simulator
make stats     # link.status becomes "DOWN" with a reason in "last_error"
make up        # bring the simulator back
make stats     # link.status returns to "UP"
```

## Video stream (MediaMTX + virtual camera)

A virtual camera (ffmpeg, test pattern or looped file) publishes to MediaMTX
path `street`, viewable in a browser over WebRTC.

```
sim-camera --RTSP--> MediaMTX "street" --WebRTC--> browser
                                       --RTSP----> workers
```

```
cp .env.example .env    # once; .env is per-machine and gitignored
make up                 # simulator + MediaMTX + virtual camera
make logs
make down
```

| What | Where |
| --- | --- |
| Stream in a browser (WebRTC) | http://localhost:8889/street/ |
| Stream for players and workers (RTSP) | `rtsp://localhost:8554/street` |
| Control API | `bin/curl-mediamtx-api` |
| Prometheus metrics | `bin/curl-mediamtx-metrics` |

Every frame carries a millisecond wall-clock timestamp and a frame counter, so
glass-to-glass latency can be read from one screenshot next to a clock.
Settings are documented in `.env.example`.

Docs: `docs/media-gateway.md` (why RTSP in, WebRTC out), `docs/ice.md`
(WebRTC through Docker, `LAN_IP`), `docs/video-stream-design.md` (decisions),
`docs/prod-checklist.md` (what to lock down before real use).

## Overview / Decisions

- uav_gc/link.py - Owns connection. Establishes and maintains link, manages callbacks
- uav_gc/vehicle.py - Owns telemetry.
- uav_gc/command.py - Encodes command, helps getting ack
- uav_gc/api.py - HTTP Api.
- Didn't differentiate command failure modes because there were no use-cases for this
- Link robustness is a top priority

## Afterthoughts

- Missing jitter on backoff to prevent retry storm
- Telemetry subscription check doesn't check interval
- Telemetry other than heartbeat is being resubscribed on link down/up, but not when vehicle stops sending telemetry (for some other reasons not reported by ACK, e.g. reboot)
- Didn't validate telemetry vals against current expectations (didn't have time yet)
