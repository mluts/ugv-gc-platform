# Prod checklist

`sim` is open and testable by design. Before real use:

Security
- [ ] Require auth on streams (change #2: nginx `auth_request`).
- [ ] Stop publishing the control API (`9997`) and metrics (`9998`).
- [ ] Change `auth.secret` in `config.toml` (the shipped example secret is a development placeholder; the bridge warns while it is in use).
- [ ] Change `users.admin_password` in `config.toml` before the first start (the example ships `admin` / `admin`).

Ports / reachability
- [ ] Publish only `8889` (WebRTC) and `8189` (ICE); `8554` only for remote RTSP readers.
- [ ] Set `LAN_IP` to the host's reachable address for `make up` (Linux alternative: `network_mode: host`).
- [ ] Add `udp` to `rtspTransports` only if a reader needs it (map `8000/8001`).
- [ ] Set `webrtcIPsFromInterfaces: false` and list hosts explicitly.
- [ ] Enable `hls` only for the latency comparison.

Settings: `deploy/mediamtx/mediamtx.yml` (static) + `compose.yaml` `MTX_*` from the environment. Rationale: `docs/video-stream-design.md`.
