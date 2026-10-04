# Tasks

## 1. Rover simulator in Compose

- [ ] 1.1 Switch `sitl/Dockerfile` to `ARDUPILOT_TAG=Rover-4.7.0`, `./waf rover` and `SITL_FRAME=rover`, update the tag in its comment links, and switch `sitl/entrypoint.sh` to `-v Rover`; verify `docker build sitl` succeeds
- [ ] 1.2 Add the `sitl` service to `compose.yaml` (`build: ./sitl`, `profiles: [sim]`, `tty` and `stdin_open`, `extra_hosts` for `host.docker.internal`, port `127.0.0.1:5762:5762`, `SITL_SPEEDUP` passed through from `.env`) and document `SITL_SPEEDUP` in `.env.example`; verify `docker compose --profile sim up sitl` keeps running for 60 seconds with MAVProxy alive in the logs. If MAVProxy exits, apply the `--no-mavproxy` fallback from `design.md` and record it there
- [ ] 1.3 Point the Makefile at Compose: `sitl` runs the simulator service in the foreground, `kill` kills it, `build` builds the images, and `uav-sitl` / `rm-uav-sitl` are removed; verify `make sitl` starts the rover and `make kill` from another terminal stops it
- [ ] 1.4 Verify the host-run bridge against the rover: with `make sitl` running, `make run-tcp` reports link `UP` and `make stats` shows a Rover mode

## 2. Check script on Rover

- [ ] 2.1 Change `scripts/check_sitl.py` to switch to `HOLD`, then `MANUAL`, arm, and disarm before exiting; verify `make check-tcp` exits 0 against `make sitl`
- [ ] 2.2 Verify `make check` (UDP through MAVProxy) exits 0 against `make sitl`, or remove `check` and `run-udp` if the `--no-mavproxy` fallback was applied in 1.2

## 3. Bridge in Compose

- [ ] 3.1 Make `MavLink.protocol_version()` return `None` before the first connection; verify `make run-tcp` with no simulator running answers `make stats` with a non-`UP` link instead of a 500
- [ ] 3.2 Read `HTTP_HOST` and `HTTP_PORT` in `uav_gc/__main__.py` and pass them to `Api.serve`; verify `HTTP_PORT=8081 make run-tcp` serves `/stats` on 8081 and the defaults are unchanged
- [ ] 3.3 Add `deploy/bridge/Dockerfile` and a root `.dockerignore`; verify `docker build -f deploy/bridge/Dockerfile .` succeeds and the image starts `python -m uav_gc --help`
- [ ] 3.4 Add the `bridge` service to `compose.yaml` (no profile, no `depends_on`, command `--tcp sitl:5762`, `HTTP_HOST=0.0.0.0`, port `127.0.0.1:8080:8080`, `restart: unless-stopped`); verify `docker compose config` is valid with and without `--profile sim`

## 4. Stack behaviour and docs

- [ ] 4.1 Verify start-up: `make up` with built images reports link `UP` on `make stats` within 60 seconds and `armable` true within 120 seconds
- [ ] 4.2 Verify ground commands over HTTP: `POST /mode?newmode=hold`, `manual` and `guided` succeed, `newmode=land` fails with an unknown-mode error, and `POST /arm` then `/disarm` in `MANUAL` flip `armed`
- [ ] 4.3 Verify link loss and recovery: after `make kill` the link is not `UP` within 10 seconds with a reason in `last_error`; after `make up` it is `UP` again within 60 seconds without restarting the bridge
- [ ] 4.4 Verify the bridge without a simulator: `docker compose up -d bridge` alone serves `/stats` with a non-`UP` link
- [ ] 4.5 Verify exposure: `curl 127.0.0.1:8080/stats` answers and `curl <LAN address>:8080/stats` is refused
- [ ] 4.6 Update `README.md`: prerequisites, quickstart with `make build` and `make up`, the two loops (full stack and host-run), Rover mode examples in place of `guided` / `land`, the `/stats` sample, and the link-loss demo; verify every command in the quickstart runs as written
- [ ] 4.7 Run `openspec validate rover-compose --strict` and verify it passes
