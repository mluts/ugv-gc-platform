# Design: virtual camera stream

NOTE: Imported from the archie project's `virtual-camera-stream` change
(2026-10-01). References to later changes (nginx auth, camera registry,
`mac-native`/`edge` profiles) are archie's roadmap, not this repo's.

## Context

Greenfield repository: no code, no Compose stack.

Development host is a Mac (Docker Desktop), which matters for WebRTC: containers
sit behind Docker's NAT and UDP port mapping is the classic failure point for
ICE.

## Goals / Non-Goals

**Goals:**
- One `make up` on a fresh clone yields a stream playable in a browser on the host and on another LAN device.
- Latency is measurable with nothing but the stream and a clock.
- The file layout (`deploy/`, `compose.yaml` with profiles) is one later changes extend rather than replace.

**Non-Goals:**
- Automating the latency measurement (a detector reading the timestamp comes with the video pipeline).
- Multiple cameras or load; one path is enough to prove the plumbing.
- Any authentication, registry, or nginx — the next change.

## Decisions

### Camera path name is `street`
The simulator stands in for a real camera; the path name is what the camera *sees*, not how the stream is produced. The first real camera will look at the street, so the simulator publishes to `street` now and the hardware takes over the same path later with nothing downstream renamed (auth verify for camera "street", the registry entry, the console tile).

*Alternative:* `sim-cam-1`. Rejected: leaks the simulator into consumer-facing names that real hardware will later occupy.

*Alternative:* `yard`, as in the doc's auth example. Rejected: there is no yard; the example was illustrative.

### Virtual camera is ffmpeg in a container, pushing RTSP over TCP
ffmpeg runs as a `sim`-profile service with a small shell entrypoint that builds the command from environment variables (`SIM_CAMERA_SOURCE`, `SIM_CAMERA_SIZE`, `SIM_CAMERA_FPS`) and loops on failure. Publishing uses `-rtsp_transport tcp` so packets never traverse Docker's bridge over UDP. Encoding: libx264, `ultrafast`/`zerolatency`, no B-frames, GOP = 1 s (keyframe interval = fps) so WebRTC viewers start within a second and MediaMTX has frequent recovery points.

*Alternative:* native ffmpeg on the host. Rejected for `sim`: the whole point of the profile is a fresh clone with only Docker. The `mac-native` profile may revisit this for inference, not for the camera.

### Default codec is H.264
The virtual camera must be indistinguishable from a real IP camera and its output must survive MediaMTX's re-mux to WebRTC for browsers. H.264 is the common denominator for both: real RTSP cameras publish H.264, and H.264 is the interoperability floor for browser WebRTC (universal support including Safari/iOS, hardware-decoded). Combined with libx264 `ultrafast`/`zerolatency` it also keeps the software encode cheap enough for the sub-500 ms target.

*Alternative:* H.265. Rejected: slower to encode, licensing baggage, weaker browser WebRTC support.
*Alternative:* VP8/VP9. Rejected: no IP-camera precedent, so the simulator would not exercise the codec real hardware uses.
*Alternative:* AV1. Rejected: encode cost is disproportionate for a 1080p@15 plumbing test and support is the least mature.

### Default source is `testsrc2`, file is an override, missing file is fatal
`-f lavfi -i testsrc2=size=...:rate=...` needs no asset and gives motion (a moving pattern) so the encoder is doing real work. A file path in `SIM_CAMERA_SOURCE` switches to `-stream_loop -1 -re -i <file>`. If the path is set and absent, the entrypoint exits non-zero with the path in the message — a silent fallback would hide a misconfigured demo. The file is mounted read-only from the host; nothing under `deploy/` holds footage.

*Trade-off:* `testsrc2` is low-entropy, so bitrate and encoder load are unrepresentative. Fine for plumbing; load tests in `load-and-hardening` use file sources.

### Timestamp overlay: wall-clock milliseconds plus frame index
`drawtext` with `%{localtime:%F %X.%3N}` and `%{n}` (frame index). `%3N` is drawtext's millisecond extension to strftime (present in the pinned `linuxserver/ffmpeg:9.0` image), so one screenshot of the frame next to a clock yields the latency directly. The container runs with the host's timezone so the overlay matches what the viewer sees on their clock.

*Alternative:* wall-clock seconds plus frame index, on the assumption that ffmpeg has no millisecond wall-clock token. Rejected once `%3N` was verified in the image: whole seconds need a burst of captures around a second rollover to reach frame-period resolution, where milliseconds need one capture.

*Alternative:* millisecond via `pts`-derived expressions. Rejected: that is stream time, not wall time, and drifts from the viewer's clock — exactly the thing we want to measure against.

### WebRTC through Docker: fixed ICE port on both UDP and TCP, advertised host set by env
MediaMTX is configured with `webrtcLocalUDPAddress: :8189` and `webrtcLocalTCPAddress: :8189`, both ports mapped in Compose, and `webrtcAdditionalHosts` taken from `LAN_IP` in `.env` (default `127.0.0.1`). The value reaches MediaMTX as the environment variable `MTX_WEBRTCADDITIONALHOSTS`, set in `compose.yaml` where Compose expands `${LAN_IP}`; MediaMTX's `MTX_<KEY>` variables override the corresponding YAML key. Neither YAML nor MediaMTX expands `${…}` inside `mediamtx.yml`, so the file itself holds only the static default. Without an advertised host, the ICE candidates carry the container's private address and the browser cannot reach it. The TCP listener is the safety net: if Docker Desktop's UDP forwarding misbehaves, ICE falls back to TCP and the stream still plays (with somewhat higher latency, which the measurement step will show).

*Alternative:* `network_mode: host`. Rejected: not portable to Docker Desktop on macOS in the default configuration and would make the `edge` profile's networking differ from `sim`.

*Alternative:* STUN. Rejected: this is a LAN-only system with no internet by principle; the advertised host is known.

### Sim posture: open auth and TCP-only RTSP, temporary
`authInternalUsers` stays open (publish/read/playback/api/metrics for `any`) so the host — the image is `scratch`, with no shell to test from inside — can reach the API and metrics through Docker's port map; the defaults allow them from `127.0.0.1` only. `rtspTransports: [tcp]` keeps RTSP on the single mapped `8554`, since the server's UDP RTP ports are unpublished and SETUP would advertise the container address. Both exist for testability and revert for real use; see `docs/prod-checklist.md`.

*Alternative:* MediaMTX defaults. Rejected: host-side `curl`/`ffprobe` fail through Docker NAT, with no shell in the image to verify from inside.

### Latency measured by side-by-side clock
Procedure documented in the README: on the viewing device open the stream next to a page or terminal showing the current time with sub-second resolution, take a screenshot, subtract. When viewer and source are the same machine the clocks are trivially synced; across devices, note that NTP skew is part of the reading. First number goes into the README as measured, not as a target.

### Repository layout established here
```
compose.yaml            profiles: sim (later: mac-native, edge)
Makefile                up / down / logs
.env.example            LAN_IP, SIM_CAMERA_SOURCE, ...
deploy/mediamtx/        mediamtx.yml
deploy/sim/             camera entrypoint
README.md
```
This is not the monorepo decision from the doc's open questions (`api/ workers/ inference/ web/` vs separate packages) — that arrives with the first Python change. `deploy/` is compatible with either answer.

## Risks / Trade-offs

- [WebRTC never connects from a second LAN device] → `LAN_IP` misconfigured is the usual cause; README documents how to find it. TCP ICE fallback covers UDP forwarding problems. Verified explicitly by a task.
- [Latency exceeds 500 ms in Docker on macOS] → This is a finding, not a blocker: record the number, note whether ICE ended up on UDP or TCP, and revisit in `mac-native` where MediaMTX can run natively. The spec target stays; the README reports the measurement.
- [`-re` pacing drifts over long loops] → `-re` on `testsrc2` is stable; file sources with variable frame rate may drift. Measured by the 10-minute scenario.
- [MediaMTX config keys change between versions] → Pin the image tag in `compose.yaml`.
