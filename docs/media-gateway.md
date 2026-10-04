# Media Gateway: why RTSP in, WebRTC out

## The shape

```
  IP camera   RTSP (pull)  ┐                        ┌─ WebRTC ──▶ browser        <1 s
  ffmpeg sim  RTSP (push)  ├──▶  MediaMTX  ────────┼─ LL-HLS ──▶ browser        2–6 s
  phone       WHIP         ┘     path "street"      └─ RTSP ────▶ python worker
```

One input per camera, re-packaged for whatever each reader can play.

## Why RTSP in

It is what cameras speak. IP cameras **serve** RTSP (MediaMTX pulls:
`source: rtsp://…`); the simulator and ffmpeg **push** RTSP (publish). Same path
either way, so hardware replaces the simulator with one config line.

## Why WebRTC out

Browsers cannot play `rtsp://`. Of what they can play, only WebRTC meets the
`< 500 ms` target:

| Browser can play | Latency | Notes |
| --- | --- | --- |
| **WebRTC** | 200–500 ms | UDP, frame-by-frame; needs ICE (see `ice.md`) |
| LL-HLS | 2–6 s | HTTP segments; off in change #1 (`hls: false`), enable later for the comparison number |
| MSE over WebSocket | ~1 s | custom player code |
| MJPEG | ~300 ms | no H.264, huge bandwidth |

All the ICE / `LAN_IP` / Docker-NAT complexity exists **only** for browser
viewing. Workers read plain RTSP from the gateway.

## Why a gateway at all

- Cameras allow 1–3 RTSP clients. The gateway fans one stream out to the
  detector, recorder, console and load tests.
- One place to hang auth (`nginx auth_request`), recording and phone intake later.

Design decisions: `docs/video-stream-design.md`.
