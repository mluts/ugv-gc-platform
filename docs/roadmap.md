# Roadmap

Capability graph from `ugv-gc-doc.md`, kept current:
the archive step of every change marks its node done
and names the next unblocked one.

Legend: `[done]` archived, `[next]` unblocked and chosen, blank: blocked.

```
    rover-sitl [done]      http-api [done]      typechecking [done]
                               |
                        auth-and-roles [next]
                        /              \
             telemetry-stream        video-gateway
              /        \                  |
     operator-console  command-queue   video-player
                        /        \
                 ws-client    manual-control
                        \        /
                      operator-input
```

| Capability       | Change                   | Depends on                | Status |
| ---------------- | ------------------------ | ------------------------- | ------ |
| rover-sitl       | rover-compose            | none                      | done   |
| http-api         | fastapi-api              | none                      | done   |
| typechecking     | pyright-typecheck        | none                      | done   |
| auth-and-roles   | auth-roles               | http-api                  | next   |
| telemetry-stream | live-telemetry           | auth-and-roles            |        |
| operator-console | live-telemetry           | telemetry-stream          |        |
| ws-client        | live-telemetry, commands | command-queue             |        |
| command-queue    | commands                 | telemetry-stream          |        |
| video-gateway    | video                    | auth-and-roles            |        |
| video-player     | video                    | video-gateway             |        |
| manual-control   | manual-drive             | command-queue             |        |
| operator-input   | manual-drive             | manual-control, ws-client |        |

`typechecking` was not in the doc's plan;
it was added as infrastructure after `fastapi-api`.

## Order of changes

1. `rover-compose`: done, archived 2026-10-05.
2. `fastapi-api`: done, archived 2026-10-06.
3. `auth-roles`: next.
4. `live-telemetry`: `telemetry-stream`, `operator-console`,
   and the connect and reconnect part of `ws-client`.
5. `commands`: `command-queue` and the client-side queue of `ws-client`.
6. `video`: `video-gateway`, `video-player`.
   Independent of `commands`; stream access goes through nginx `auth_request`.
7. `manual-drive`: `manual-control`, `operator-input`.
8. `demo`: README with measured latencies, a short screen recording,
   a description of how changes were sliced and reviewed.

## Deferred, not on the graph

Link hardening from the README afterthoughts:
backoff jitter, telemetry interval check,
resubscribing when the vehicle goes silent without the link dropping.
The six requirements do not depend on it.
