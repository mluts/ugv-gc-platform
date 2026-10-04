# Spec Delta

## Purpose

Provides the simulated ground vehicle every other capability is built and tested against: an ArduPilot Rover simulator and the vehicle bridge, started together with one command and resilient to the simulator starting late, stopping or restarting.

## ADDED Requirements

### Requirement: Simulated vehicle is a ground rover
The simulator SHALL run an ArduPilot Rover with steering and throttle control, and the bridge SHALL report and command it as a ground vehicle.

#### Scenario: State reports a ground mode
- **WHEN** the stack is running and the bridge's state endpoint is requested
- **THEN** the reported mode is a Rover mode (for example `MANUAL` or `HOLD`), never a Copter-only mode such as `STABILIZE`

#### Scenario: Ground mode change is accepted
- **WHEN** a mode change to `HOLD`, `MANUAL` or `GUIDED` is requested through the bridge
- **THEN** the request succeeds and the state endpoint reports the new mode

#### Scenario: Copter-only mode is rejected
- **WHEN** a mode change to `LAND` is requested through the bridge
- **THEN** the request fails with an error naming the unknown mode and the vehicle's mode is unchanged

#### Scenario: Arm and disarm
- **WHEN** the vehicle is armable in `MANUAL` and arm is requested, then disarm is requested
- **THEN** each request succeeds and the state endpoint reports `armed` as true, then false

### Requirement: One command starts the vehicle stack
`make up` SHALL start the simulator and the bridge together with the existing video services, with no other manual step beyond creating `.env`.

#### Scenario: Stack comes up connected
- **WHEN** `make up` is run with the images already built
- **THEN** within 60 seconds the bridge's state endpoint reports the vehicle link as `UP`

#### Scenario: Vehicle becomes armable
- **WHEN** the stack has been up for 120 seconds at simulation speed 1
- **THEN** the state endpoint reports `armable` as true

#### Scenario: One command stops the stack
- **WHEN** `make down` is run
- **THEN** the simulator, the bridge and the video services are all stopped and removed

### Requirement: Bridge tolerates an absent simulator
The bridge SHALL keep serving its state endpoint whenever the simulator is unreachable, and SHALL connect or reconnect on its own without being restarted.

#### Scenario: Bridge starts before the simulator
- **WHEN** the bridge is running and the simulator has never been reachable
- **THEN** the state endpoint answers successfully and reports the vehicle link as not `UP`

#### Scenario: Simulator is killed
- **WHEN** the simulator is killed with `make kill` while the link is `UP`
- **THEN** within 10 seconds the state endpoint reports the link as not `UP` together with the reason

#### Scenario: Simulator returns
- **WHEN** the simulator is started again after being killed
- **THEN** within 60 seconds the state endpoint reports the link as `UP` and telemetry ages are fresh again, with no action taken on the bridge

### Requirement: Bridge API is reachable from the host only
The bridge's HTTP API SHALL be reachable on the host's loopback interface and SHALL NOT be reachable from other machines, because it has no authentication.

#### Scenario: Reachable on loopback
- **WHEN** the stack is running and `http://127.0.0.1:8080/stats` is requested on the host
- **THEN** the bridge answers with the vehicle state

#### Scenario: Not reachable from the network
- **WHEN** the stack is running and port 8080 is requested on the host's LAN address
- **THEN** the connection is refused

### Requirement: Simulator can run alone for a host-run bridge
The simulator SHALL be startable without the Compose bridge, exposing its MAVLink endpoint on the host's loopback, so the bridge and the check script can run directly on the host.

#### Scenario: Host-run bridge connects
- **WHEN** `make sitl` is running and `make run-tcp` is started on the host
- **THEN** the host-run bridge reports the link as `UP`

#### Scenario: Check script passes against the rover
- **WHEN** `make sitl` is running and `make check-tcp` is run
- **THEN** the script passes heartbeat, prearm, armable, mode change and arm, and exits with status 0
