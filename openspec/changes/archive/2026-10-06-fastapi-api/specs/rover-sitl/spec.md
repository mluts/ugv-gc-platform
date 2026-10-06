# Spec Delta

## MODIFIED Requirements

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

### Requirement: Bridge listen address is configurable
The bridge SHALL listen on the loopback interface, port 8080, unless configured otherwise, and SHALL accept a different listen host and port through its environment, so the same code can run on the host or in a container.

#### Scenario: Default is loopback only
- **WHEN** the bridge is started with no listen configuration
- **THEN** the state endpoint answers on `127.0.0.1:8080` and port 8080 on the host's LAN address refuses connections

#### Scenario: Listen address overridden
- **WHEN** the bridge is started with a listen port of 8081 configured
- **THEN** the state endpoint answers on port 8081 and not on 8080
