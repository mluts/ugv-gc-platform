#!/bin/sh
set -e

exec /ardupilot/Tools/autotest/sim_vehicle.py \
     -v ArduCopter -f "$SITL_FRAME" \
     --no-rebuild \
     --speedup "$SITL_SPEEDUP" \
     --custom-location "$SITL_HOME" \
     --out udp:host.docker.internal:14550
