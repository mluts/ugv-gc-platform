# Deployment scenarios

The demo runs entirely on one laptop against Rover SITL. This note maps that
shape onto real deployments: what each piece becomes, the links between them,
and the gaps that must close before field use.

## What has to be placed

The system is four pieces joined by three kinds of link.

| Piece | In the demo | Placement question |
| --- | --- | --- |
| Autopilot (ArduPilot) | Rover SITL in Docker | Fixed on the vehicle; not a choice. |
| Bridge (`uav_gc`) | Python on the host, `tcp:127.0.0.1:5762` | **Onboard or offboard** — the main axis. |
| MediaMTX + camera | Docker, `LAN_IP`, ICE on `8189` | Follows the camera; onboard if the camera is. |
| Operator (browser console) | `localhost:8889` | Wherever the human is, on some path to the server. |

The `link.device` endpoint (`tcp:` / `udpin:` / serial) and the
`HTTP_HOST` / `LAN_IP` bindings are the knobs that define a deployment;
everything else is the same binary.

## Where the bridge runs

1. **Offboard.** Bridge on a laptop or base station, reaching the autopilot over
   a telemetry radio, Wi-Fi, or a cable. Simple, but the bridge-to-autopilot
   hop is now a second fragile link that `link.py` supervises only coarsely
   (link loss surfaces as rejected commands).
2. **Onboard companion.** Bridge and MediaMTX on a Pi or Jetson wired to the
   flight controller over UART (`--serial`). The operator link is the only
   network in play. This is the shape `ugv-gc-doc.md` points at.
3. **Hybrid.** Telemetry bridge onboard, video gateway and console offboard on
   a more capable base station.

## Scenario catalogue

| # | Scenario | Bridge | Operator link | What needs attention |
| --- | --- | --- | --- | --- |
| A | Bench / lab | Laptop, TCP or serial | none (local) | Nothing; `make up` with a Pixhawk on USB. |
| B | Line-of-sight field, Wi-Fi | Onboard companion | Operator on the same Wi-Fi | `LAN_IP` correct; stream auth unbuilt; ICE through the AP. |
| C | Line-of-sight field, telemetry radio | Base station, `--serial` | none | Bridge-to-autopilot is the weak link; no video over 433/915 MHz. |
| D | Remote over LTE/4G | Onboard companion + SIM | Internet + VPN | Repo is LAN-only (no STUN/TURN); candidates and video budget. |
| E | Fixed base station, high-gain radio | Base station | Operator LAN | Long-range telemetry only; no video. |
| F | Multi-vehicle | One bridge per vehicle | shared console | Out of scope: single `link`, single camera. |

## 1. Onboard companion + Wi-Fi operator

    Rover
    ├── Flight controller (Pixhawk) ── TELEM2 UART ──▶ Companion SBC (Pi 5 / Jetson Orin Nano)
    ├── Camera (CSI / USB / IP) ──── RTSP or WHIP ───▶ MediaMTX on the companion
    └── Wi-Fi (AP on the rover, or a venue AP) ◀── operator laptop / tablet browser

| Process | How it runs | Configuration |
| --- | --- | --- |
| Bridge (`uav_gc`) | `python -m uav_gc --serial /dev/ttyAMA0 --baud 921600` | `HTTP_HOST=0.0.0.0` |
| MediaMTX + camera | Docker Compose (`sim` services, real camera) | `LAN_IP` = companion Wi-Fi IP |
| Console | served from the same box (planned) | — |

Why this is the default: the autopilot link becomes a short UART you control,
and the only network in play is the operator link.

Gotchas:

- **No config-file startup.** A fielded robot wants `systemd` units, and those
  want `ExecStart=… --config /etc/ugv/config.toml`, not env guesswork. Wiring
  `load_config()` into `__main__` is a prerequisite; today the TOML `[link]`
  section is ignored (`__main__` uses `argparse` and `HTTP_HOST`/`HTTP_PORT`).
- **UART setup.** Disable the Pi's serial console, enable the port, mount the
  device into the unit. MAVLink2 at 921600 is the usual value.
- **Wi-Fi is the whole operator link.** `docs/ice.md` explains the `LAN_IP`
  Docker hack. On a Linux companion prefer `network_mode: host` and set
  `webrtcIPsFromInterfaces: false` with explicit hosts. Roaming changes the
  IP and invalidates the advertised candidate.
- **Power and thermal.** Jetson plus MediaMTX software transcode runs hot; use
  hardware encode and 720p.
- **Boot to operation.** Power loss is normal; the bridge must start
  independently of the vehicle link (`supervise()` already tolerates a late
  autopilot), and MediaMTX must restart cleanly.

## 2. Remote over LTE/4G + VPN

    Rover: FC ─UART─ bridge + MediaMTX ── 4G modem / hotspot
                                            │
                                       (NAT / CGNAT)
                                            │
                                  WireGuard / Tailscale VPN
                                            │
                                  Operator browser ──VPN── console

The repo is deliberately LAN-only with no STUN or internet (`docs/ice.md` §7),
so LTE breaks three assumptions:

1. **Candidate reachability.** Host candidates are RFC1918 addresses that
   carrier CGNAT will not forward. In order of preference: put both ends on a
   WireGuard/Tailscale overlay so host candidates are reachable through the
   tunnel; run a TURN relay; or use the TCP ICE listener only. Do not add STUN
   by hand — it was removed on purpose.
2. **Bandwidth.** 1080p15 H.264 is ~2–4 Mbps; LTE uplink is often 1–5 Mbps and
   metered. Drop to 720p, cap the bitrate, and treat HLS (2–6 s) as unusable.
   WebRTC's 200–500 ms on LAN becomes 300–800 ms through LTE plus VPN.
3. **Cost and reliability.** Carrier CGNAT drops idle mappings; keep-alives
   matter. Re-tune the dead man's switch for LTE jitter — 500 ms to neutral is
   aggressive when RTT can spike past it.

Concrete changes: `webrtcIPsFromInterfaces: false`, list the tunnel host, no
STUN, keep TCP ICE as a fallback, and expect a TURN relay on hostile carriers.
The bridge itself is unchanged over the tunnel.

## 3. Fixed base station (telemetry radio only)

    Vehicle FC ──▶ SiK / RFD900 radio (433/915 MHz) ~~~km LOS~~~ base radio ──USB──▶ base mini-PC
                                                                                       └── bridge --serial /dev/ttyUSB0
    Operator on base LAN ──▶ console (HTTP)

- **No video.** 433/915 MHz carries MAVLink, not 2–4 Mbps H.264. This is
  telemetry and discrete commands only.
- **Bridge as a `systemd` service** on the base PC, `--serial /dev/ttyUSB0
  --baud 57600` (SiK default), or `--udp`/`--tcp` if the radio ground unit
  exposes an IP bridge (RFD900 does).
- **The bridge-to-autopilot hop is now the fragile one.** `link.py` supervises
  it and the watchdog fires after `HEARTBEAT_TIMEOUT = 5 s`, but `RADIO_STATUS`
  / RSSI is not surfaced, so a degrading radio is invisible to the operator.
  This is where the README afterthoughts actually bite.
- **Optional fan-out.** `mavlink-router` can share one radio across the bridge
  and a logging tool. Do not point two clients at one TCP endpoint — the SITL
  TCP path is single-client and `link.py` notes the "tcp doom loop".

## 4. Gap list for real use

### Blockers before any field use

1. **No auth on the HTTP API or streams.** Roadmap: `auth-roles` is next, the
   video `auth_request` change after it. Until then anyone who can reach the
   port can arm the vehicle.
2. **No TLS.** uvicorn serves plain HTTP; JWT HS256 tokens and the API are in
   cleartext. Put nginx/Caddy in front (which also provides `auth_request`).
3. **Loopback default vs. remote bind.** `HTTP_HOST=127.0.0.1` is right on the
   bench; a fielded bridge binds `0.0.0.0` behind the reverse proxy, never
   directly.
4. **MediaMTX control API (`9997`) and metrics (`9998`) published.** Stop
   publishing them (`docs/prod-checklist.md`).
5. **Config-file startup.** Wire `load_config()` into `__main__`.

### Hardening for reliable operation

6. **Link robustness** (README afterthoughts): backoff jitter, telemetry
   interval check, resubscribe when the vehicle goes silent without the link
   dropping (e.g. its reboot).
7. **Survive network change.** Wi-Fi/LTE IP changes invalidate WebRTC
   candidates and drop the operator link.
8. **Time sync.** `age_s` markers and the burned-in video clock assume a shared
   clock; run chrony/NTP on the companion.

### Safety and operations, not code

9. **RC override stays primary.** The GCS is a secondary path; the transmitter
   and a physical e-stop must always win.
10. **Failsafe semantics.** Rover "stop on link loss" is safe; define geofence
    and what HOLD means on the chassis.
11. **Radio, power, enclosure.** Antenna placement, band licensing, power
    budget, thermal, vibration, IP rating.
