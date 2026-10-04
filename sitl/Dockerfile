FROM ubuntu:24.04 AS builder

# https://github.com/ArduPilot/ardupilot/tree/Copter-4.7.0
ARG ARDUPILOT_TAG=Copter-4.7.0
ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates build-essential \
    python3 python3-pip \
    && rm -rf /var/lib/apt/lists/* # we don't need index

# empy: https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.0/Tools/environment_install/install-prereqs-ubuntu.sh#L197
# pymavlink: https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.0/Tools/autotest/sim_vehicle.py
# pexpect: https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.0/Tools/autotest/sim_vehicle.py
# future: python2 compat
RUN pip3 install --break-system-packages \
    empy==3.3.4 pexpect future pymavlink

RUN git clone --branch ${ARDUPILOT_TAG} --depth 1 \
    --recurse-submodules --shallow-submodules \
    https://github.com/ArduPilot/ardupilot.git /ardupilot

WORKDIR /ardupilot

RUN ./waf configure --board sitl && ./waf copter

FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip procps psmisc \
    && rm -rf /var/lib/apt/lists/* # we don't need index

RUN pip3 install --break-system-packages \
    MAVProxy pexpect pymavlink future

COPY --from=builder /ardupilot /ardupilot

WORKDIR /ardupilot

ENV SITL_FRAME=quad \
    SITL_SPEEDUP=1 \
    SITL_HOME=-35.363261,149.165230,584,353
    # CMAC https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.0/Tools/autotest/locations.txt#L4

# simulator exposes to 5760, 5762, 5763
# 5760 is taken immediately by simulator CLI, use next one
EXPOSE 5762/tcp

COPY entrypoint.sh /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
