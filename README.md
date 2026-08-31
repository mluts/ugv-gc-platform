# uav-gc-platform

Ground-control platform.

MAVLink telemetry bridge + vehicle cmd API.

Tested against ArduPilot SITL in Docker.

## Prerequisites

- Docker
- GNU make
- uv (installs python 3.13)
- curl + jq

## Quickstart

```
uv sync
make sitl # builds docker image

make run-tcp # run service on 127.0.0.1:8080 using SITL SERIAL1 via TCP
# or
make run-udp # run service on 127.0.0.1:8080 using UDPIN on 127.0.0.1:14550

```
## HTTP API

```
curl '127.0.0.1:8080/stats'
curl -XPOST '127.0.0.1:8080/arm'
curl -XPOST '127.0.0.1:8080/disarm'
curl -XPOST '127.0.0.1:8080/mode?newmode=guided'
curl -XPOST '127.0.0.1:8080/mode?newmode=land'
```

Example

```
make stats

curl 127.0.0.1:8080/stats | jq
{
  "position": {
    "lat": 0.0,
    "lon": 0.0,
    "alt_msl": 0.0,
    "alt_rel": 0.0,
    "vn": 0.0,
    "ve": 0.0,
    "vd": 0.06,
    "heading": 340.2,
    "age_s": 0.43
  },
  "attitude": {
    "roll": 0.00008774105663178489,
    "pitch": -0.000018347001969232224,
    "yaw": -0.3456156849861145,
    "age_s": 0.03
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
      "age_s": 0.53
    }
  ],
  "mode": "STABILIZE",
  "armed": false,
  "armable": false,
  "position_ok": false,
  "link": {
    "status": "UP",
    "last_error": null,
    "heartbeat_age_s": 1
  },
  "ts": 1788031878.883144
}
```

## Overview / Decisions

- uav_gc/link.py - Owns connection. Establishes and maintains link, manages callbacks
- uav_gc/vehicle.py - Owns transport telemetry.
- uav_gc/command.py - Encodes command, helps getting ack
- uav_gc/api.py - HTTP Api.
- Didn't differentiate command failure modes because there were no use-cases for this
- Link robustness is a top priority

## Afterthoughts

- Missing jitter on backoff to prevent retry storm
- Telemetry subscription check doesn't check interval
- Telemetry other than heartbeat is being resubscribed on link down/up, but not when vehicle stops sending telemetry (for some other reasons)
