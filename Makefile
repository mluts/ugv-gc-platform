.PHONY: run stats sitl kill typecheck test-fast test repl ardupilotmega up down logs build

# NOTE: Every target passes the profile, otherwise `down` and `logs` ignore sim-profile services.
COMPOSE := docker compose --profile sim

# Video stack: MediaMTX + virtual camera (see docs/media-gateway.md)
up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

run:
	PYTHONPATH=. ./.venv/bin/python3 -m uav_gc

stats:
	bin/curl-api /vehicle/state | jq

sitl:
	$(COMPOSE) up sitl

kill:
	$(COMPOSE) kill sitl

build:
	$(COMPOSE) build

# NOTE: Static types on the production package only; tests stay duck-typed.
typecheck:
	./.venv/bin/pyright uav_gc

test-fast: typecheck
	PYTHONPATH=. ./.venv/bin/python3 -m pytest -m "not sitl"

test: typecheck
	PYTHONPATH=. ./.venv/bin/python3 -m pytest

repl:
	PYTHONSTARTUP="$(CURDIR)/.pythonstartup.py" ./.venv/bin/python3

ardupilotmega:
	nvim "$$(./.venv/bin/python3 -c 'import pymavlink; from pathlib import Path; print(Path(pymavlink.__file__).parent / "dialects/v20/ardupilotmega.py")')"
