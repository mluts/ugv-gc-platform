# Spec Delta

## ADDED Requirements

### Requirement: Bridge is configured by one file
The bridge SHALL read its settings from `config.toml` (or the `--config` path) and validate
it before opening the link or listening. On a missing file, unknown key, wrong type, missing
key, or missing required section (`[link]`, `[auth]`), it exits non-zero naming the path, key
or section. A relative `users.database` resolves against the file's directory. `link.device`
selects the vehicle connection as a pymavlink device string, with `link.baud` for serial.

#### Scenario: Missing file
- **WHEN** the bridge is started with no `config.toml` and no `--config`
- **THEN** it exits non-zero and the message names `config.toml`

#### Scenario: Unknown key
- **WHEN** the bridge is started with a configuration file holding `[http]` `prot = 8080`
- **THEN** it exits non-zero and the message names `prot`

#### Scenario: Wrong type
- **WHEN** the bridge is started with a configuration file holding `[http]` `port = "eighty"`
- **THEN** it exits non-zero and the message names `port`

#### Scenario: Missing section
- **WHEN** the bridge is started with a configuration file with no `[auth]` section
- **THEN** it exits non-zero and the message names `auth`

#### Scenario: Relative path
- **WHEN** the bridge is started with `--config /elsewhere/config.toml` holding `users.database = "data/users.db"`
- **THEN** the database is created at `/elsewhere/data/users.db`

#### Scenario: Link from the file
- **WHEN** the simulator is running and the bridge is started with `link.device = "tcp:127.0.0.1:5762"`
- **THEN** within 60 seconds the state endpoint reports the vehicle link as `UP`

## MODIFIED Requirements

### Requirement: One command starts the simulators
`make up` SHALL start the Rover simulator together with the existing video services, with no manual step,
and SHALL expose the simulator's MAVLink endpoint on the host's loopback interface only.
Every simulator setting SHALL have a default in `compose.yaml`, so no configuration file or copy step is needed;
a setting SHALL be overridable by exporting its variable for the `make up` invocation.

#### Scenario: Host-run bridge connects
- **WHEN** `make up` has been run with the images already built and `make run` is started on the host with the example configuration
- **THEN** within 60 seconds the bridge's state endpoint reports the vehicle link as `UP`

#### Scenario: Starts with no configuration
- **WHEN** `make up` is run with no `.env` file and no exported variables
- **THEN** the simulator, MediaMTX and the virtual camera all start, and the stream is viewable on `127.0.0.1`

#### Scenario: Setting overridden
- **WHEN** `make up` is run with `LAN_IP` exported to the host's LAN address
- **THEN** MediaMTX advertises that address as its WebRTC ICE host

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
The bridge SHALL listen on the loopback interface, port 8080, unless `http.host` and `http.port` in its configuration file say otherwise,
so the same code can run on the host or in a container with a mounted file.

#### Scenario: Default is loopback only
- **WHEN** the bridge is started with no `[http]` section in its configuration file
- **THEN** the state endpoint answers on `127.0.0.1:8080` and port 8080 on the host's LAN address refuses connections

#### Scenario: Listen address overridden
- **WHEN** the bridge is started with `http.port = 8081` in its configuration file
- **THEN** the state endpoint answers on port 8081 and not on 8080
