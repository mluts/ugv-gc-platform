.PHONY: run-udp run-tcp stats sitl kill check check-tcp repl uav-sitl rm-uav-sitl ardupilotmega

run-udp: 
	PYTHONPATH=. ./.venv/bin/python3 -m uav_gc --udp 0.0.0.0:14550

run-tcp: 
	PYTHONPATH=. ./.venv/bin/python3 -m uav_gc --tcp 127.0.0.1:5762

stats:
	curl 127.0.0.1:8080/stats | jq

sitl: uav-sitl
	docker run --name uav-sitl -it --rm --add-host=host.docker.internal:host-gateway -p 127.0.0.1:5762:5762 uav-sitl

kill:
	docker kill uav-sitl

check:
	PYTHONPATH=. ./.venv/bin/python3 ./scripts/check_sitl.py --udp 0.0.0.0:14550

check-tcp:
	PYTHONPATH=. ./.venv/bin/python3 ./scripts/check_sitl.py --tcp 127.0.0.1:5762

repl:
	PYTHONSTARTUP="$(CURDIR)/.pythonstartup.py" ./.venv/bin/python3

uav-sitl:
	docker build -t uav-sitl sitl

rm-uav-sitl:
	docker image rm uav-sitl

ardupilotmega:
	nvim "$$(./.venv/bin/python3 -c 'import pymavlink; from pathlib import Path; print(Path(pymavlink.__file__).parent / "dialects/v20/ardupilotmega.py")')"
