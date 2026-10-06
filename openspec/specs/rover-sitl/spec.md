# rover-sitl Specification

## Purpose

Provides the simulated ground vehicle every other capability is built and tested against: an ArduPilot Rover simulator started from the Compose stack, and a vehicle bridge that runs on the host and stays connected through the simulator starting late, stopping or restarting.

## Requirements

### Requirement: Simulated vehicle is a ground rover
The simulator SHALL run an ArduPilot Rover with steering and throttle control, and the bridge SHALL report and command it as a ground vehicle.

#### Scenario: State reports a ground mode
- **WHEN** the simulator and the bridge are running and the bridge's state endpoint is requested
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

### Requirement: One command starts the simulators
`make up` SHALL start the Rover simulator together with the existing video services, with no other manual step beyond creating `.env`, and SHALL expose the simulator's MAVLink endpoint on the host's loopback interface only.

#### Scenario: Host-run bridge connects
- **WHEN** `make up` has been run with the images already built and `make run-tcp` is started on the host
- **THEN** within 60 seconds the bridge's state endpoint reports the vehicle link as `UP`

#### Scenario: Vehicle becomes armable
- **WHEN** the simulator has been up for 120 seconds at simulation speed 1 with the bridge connected
- **THEN** the state endpoint reports `armable` as true

#### Scenario: Simulator alone in the foreground
- **WHEN** `make sitl` is run
- **THEN** only the simulator starts, with its output attached to the terminal

#### Scenario: One command stops the simulators
- **WHEN** `make down` is run
- **THEN** the simulator and the video services are all stopped and removed

#### Scenario: Simulator test suite passes against the rover
- **WHEN** no bridge is connected to the simulator and `make test` is run
- **THEN** the simulator tests start the simulator if it is not running, pass heartbeat, armable, mode change, arm and disarm, and the run exits with status 0

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

### Requirement: Bridge listen address is configurable
The bridge SHALL listen on the loopback interface, port 8080, unless configured otherwise, and SHALL accept a different listen host and port through its environment, so the same code can run on the host or in a container.

#### Scenario: Default is loopback only
- **WHEN** the bridge is started with no listen configuration
- **THEN** `http://127.0.0.1:8080/stats` answers and port 8080 on the host's LAN address refuses connections

#### Scenario: Listen address overridden
- **WHEN** the bridge is started with a listen port of 8081 configured
- **THEN** the state endpoint answers on port 8081 and not on 8080
