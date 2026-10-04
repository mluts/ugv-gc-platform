# ICE Cheatsheet

**ICE (Interactive Connectivity Establishment, RFC 8445)** is the part of WebRTC
that finds a working network path between two peers when neither side knows its
own reachable address.

> If you know SDP is "what we exchange" and RTP is "the media", ICE is
> **"how we actually connect"**.

This is a skim guide, not a spec. RFCs are linked at the bottom.

---

## 1. The problem ICE solves

A peer usually has several addresses (loopback, LAN, VPN, Docker bridge), and
the only address the *other* peer can reach is one it cannot see: the public
`ip:port` created by a NAT. Firewalls make it worse — even a known address may
drop unsolicited packets.

```
         ┌────────────┐                       ┌────────────┐
         │   Peer A   │                       │   Peer B   │
         │ 10.0.0.5   │                       │ 192.168.1.7│
         └─────┬──────┘                       └──────┬─────┘
               │ NAT A                               │ NAT B
        ┌──────┴───────┐                      ┌───────┴──────┐
        │ 203.0.113.9  │◀ ─ ─ which pair? ─ ─▶│ 198.51.100.2 │
        └──────────────┘                      └──────────────┘
```

There is no DNS-style lookup for "where is this peer reachable." ICE is the
mechanism that discovers it, at connect time, by trying.

---

## 2. Vocabulary

| Term | Meaning |
| --- | --- |
| **Candidate** | One address of one peer that *might* be reachable from the other side. |
| **Host candidate** | A local interface address (`10.0.0.5:50000`). Works only on the same LAN. |
| **Server-reflexive candidate** | Your public `ip:port` as seen by a **STUN** server — the NAT mapping. |
| **Relay candidate** | An address on a **TURN** server that forwards all traffic. Last resort. |
| **STUN** | Simple protocol (RFC 5389): "what address do you see me coming from?" Also used for the connectivity checks. |
| **TURN** | Relay server (RFC 8656) used when no direct path exists. Costs bandwidth; adds latency. |
| **Gathering** | Collecting your own candidates (host, then STUN, then TURN). |
| **Connectivity check** | A STUN binding request sent from one candidate to another to test if the pair works. |
| **Pair** | A (local candidate, remote candidate) combination. ICE tests many pairs in priority order. |
| **Nomination** | Choosing the winning pair to carry media. |
| **Checklist** | The ordered set of pairs ICE is testing. |

---

## 3. The flow

```
   A                signaling (SDP)                 B
   │  gather candidates (host, STUN, TURN)            │
   │ ───────── candidates in SDP offer ─────────────▶│
   │◀──────── candidates in SDP answer ──────────────│
   │  form pairs, sort by priority                    │
   │ ── STUN connectivity check ────────────────────▶ │
   │◀─ check succeeds ─────────────────────────────── │
   │  nominate best pair                              │
   │◀═════════ media (SRTP) flows here ══════════════▶│
```

Key points:

- **Signaling is external.** ICE does not define how offers/answers travel —
  that is your signaling channel (WebSocket, HTTP, MediaMTX's WHIP, ...).
- Candidates are exchanged in **SDP**, not by ICE itself.
- **Trickle ICE** streams candidates as they are found instead of waiting for
  gathering to finish — faster setup, same result.
- Direct pairs beat relayed pairs; ICE only falls back to TURN if nothing
  direct works.

---

## 4. Where ICE sits in the WebRTC stack

| Layer | Job |
| --- | --- |
| **SDP** | Negotiate *what* is being sent (codecs, directions, candidates). |
| **ICE** | Find *where* to send it — the working network path. |
| **DTLS** | Encrypt and authenticate the transport. |
| **SRTP / SCTP** | Carry media / data once connected. |

---

## 5. Direct vs. STUN vs. TURN

| Path | When it works | Cost |
| --- | --- | --- |
| **Direct (host)** | Both peers on the same LAN, no firewall between. | Cheapest, lowest latency. |
| **STUN (server-reflexive)** | Home/office NAT with ordinary port mapping. | Cheap; no relay bandwidth. |
| **TURN (relay)** | Symmetric NAT, strict firewalls, blocked UDP. | All traffic through the relay: bandwidth + latency. |

Rule of thumb: try direct → STUN → TURN, in that order. If TURN is the only
option, your media server is paying for every byte.

---

## 6. Failure modes

| Symptom | Likely cause | Fix / check |
| --- | --- | --- |
| No candidates at all | No interfaces gathered, ICE agent never ran | Check the browser console and `chrome://webrtc-internals`. |
| Only host candidates | STUN unreachable | Confirm the STUN server is reachable on UDP. |
| Direct pair fails, relay works | Symmetric NAT or UDP blocked | Provide a TURN server, or allow the UDP port. |
| Connects locally, not from another device | Candidate carries a private address (e.g. container IP) | Advertise the correct public/LAN host — here, `MTX_WEBRTCADDITIONALHOSTS=${LAN_IP}` in `compose.yaml`. |
| Works on some networks only | UDP forwarding / Docker NAT | Fall back to a TCP ICE listener, or map the UDP port properly. |
| Random drops after connect | ICE consent freshness fails | Check packet loss on the nominated pair. |

---

## 7. In this repo

The `virtual-camera-stream` design pins ICE down to survive Docker Desktop on
macOS (see "WebRTC through Docker" in `docs/video-stream-design.md`):

- MediaMTX listens for WebRTC ICE on **both UDP and TCP** at `:8189`, and both
  are mapped in Compose.
- `LAN_IP` from `.env` puts the host's LAN address into the candidates — without
  it, candidates advertise the container's private IP and a browser on the LAN
  cannot reach them. It travels as `MTX_WEBRTCADDITIONALHOSTS: ${LAN_IP}` in
  `compose.yaml`: Compose expands `${LAN_IP}`, and MediaMTX's `MTX_<KEY>` env
  vars override YAML keys. Neither YAML nor MediaMTX expands `${…}` inside
  `mediamtx.yml`, so the value is not set there.
- The **TCP listener is the safety net**: if Docker's UDP forwarding misbehaves,
  ICE falls back to TCP and the stream still plays (with somewhat higher
  latency).
- To see which path was chosen, open `chrome://webrtc-internals` while viewing
  the stream, read the MediaMTX logs, or `curl localhost:9997/v3/webrtcsessions/list`
  (`localCandidate` / `remoteCandidate`).

**Observed (2026-10-01, MediaMTX 1.21.1, Docker Desktop on macOS):**

| Viewer | Transport | Time to first frame | Candidates MediaMTX logged |
| --- | --- | --- | --- |
| iPhone 17 Pro, Safari, same Wi-Fi | **UDP** | < 1 s | local `host/udp/127.0.0.1/8189`, remote `prflx/udp/192.168.65.1/…` |

- UDP forwarding through Docker Desktop worked, so the TCP fallback was not needed.
- The remote address is `192.168.65.1`, Docker Desktop's NAT gateway, not the
  phone's LAN IP. MediaMTX cannot see real client addresses in this setup, so
  IP-based rules and logs are useless here.

This is a **LAN-only** system with no internet by principle, so STUN is not
used — the advertised host is known. That is a deliberate simplification, not
a general ICE setup.

---

## 8. Further reading

- **RFC 8445** — Interactive Connectivity Establishment (the core spec).
- **RFC 5389** — STUN.
- **RFC 8656** — TURN.
- **RFC 8829** — JSEP (how ICE is driven in WebRTC).
- MDN: *WebRTC connectivity* and `chrome://webrtc-internals` for live view.
