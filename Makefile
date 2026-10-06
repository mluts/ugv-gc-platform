.PHONY: run-udp run-tcp stats sitl kill test-fast test repl ardupilotmega up down logs build

# NOTE: Every target passes the profile, otherwise `down` and `logs` ignore sim-profile services.
COMPOSE := docker compose --profile sim

# Video stack: MediaMTX + virtual camera (see docs/media-gateway.md)
up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

run-udp: 
	PYTHONPATH=. ./.venv/bin/python3 -m uav_gc --udp 0.0.0.0:14550

run-tcp: 
	PYTHONPATH=. ./.venv/bin/python3 -m uav_gc --tcp 127.0.0.1:5762

stats:
	curl 127.0.0.1:8080/vehicle/state | jq

sitl:
	$(COMPOSE) up sitl

kill:
	$(COMPOSE) kill sitl

build:
	$(COMPOSE) build

test-fast:
	PYTHONPATH=. ./.venv/bin/python3 -m pytest -m "not sitl"

test:
	PYTHONPATH=. ./.venv/bin/python3 -m pytest

repl:
	PYTHONSTARTUP="$(CURDIR)/.pythonstartup.py" ./.venv/bin/python3

ardupilotmega:
	nvim "$$(./.venv/bin/python3 -c 'import pymavlink; from pathlib import Path; print(Path(pymavlink.__file__).parent / "dialects/v20/ardupilotmega.py")')"
