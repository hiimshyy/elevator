# Requirements Document

## Introduction

This feature integrates the proven behavior of the standalone `test_modbus.py` script into the project's Clean Architecture structure (`domain` / `application` / `infrastructure` / `presentation`). The script reads the elevator controller's full Modbus holding-register map (~80 registers, including six error-history blocks) over RS-485 using `pymodbus`, and publishes a flat JSON snapshot to a single MQTT topic.

The integration adds controller telemetry as a **new, additive capability** alongside the existing three field-sensor reads (`ES-VS-01` vibration, `ES35-SW` temperature/humidity, `RW-ST01D` load). It must fit the target runtime flow (`RS-485/Modbus -> Gateway -> Poll use case -> SQLite + RedisQueue + MQTT -> processing -> FastAPI/WebSocket -> React frontend`) without breaking existing sensor reads, and must keep dependencies pointing inward per Clean Architecture.

### Confirmed Design Decisions

These decisions were confirmed with the product owner and are treated as binding constraints for the requirements below:

1. **Modbus library**: Use `pymodbus` `ModbusSerialClient` for the controller. The existing `minimalmodbus`-based `ModbusGateway` is retained unchanged for the three field sensors. Both libraries coexist.
2. **Scope**: Controller telemetry is an **additional** capability. The existing `ModbusGateway.read_controller()` behavior is not removed or modified by this feature.
3. **MQTT**: Both formats are supported. The existing structured topics (`embody/w`, `embody/r`) remain. A new flat-payload publish to `embody/elevator` is added.
4. **Persistence**: A new dedicated domain entity and database table store the controller register snapshot and error history. The existing `SensorReading` entity is not modified.
5. **Values**: Both raw and scaled values are persisted. The `embody/elevator` MQTT payload publishes raw register values (matching the tested script).
6. **Configuration**: All serial settings, MQTT settings, register map, and credentials are sourced from the project `Settings`/environment configuration. No hardcoded credentials or connection settings in adapter code.

## Glossary

- **Controller**: The elevator controller device on the RS-485 bus at Modbus slave/unit ID 1, exposing holding registers per the register map.
- **Controller_Gateway**: The new infrastructure adapter that reads the Controller's holding registers via `pymodbus` `ModbusSerialClient` and exposes them through a domain port.
- **Controller_Gateway_Port**: The domain interface (port) that `Controller_Gateway` implements, decoupling the application layer from `pymodbus`.
- **Register_Map**: The ordered collection of register definitions, each with address, key, meaning, display base (radix 10 or 16), scale factor, and unit.
- **Register_Entry**: A single definition within the Register_Map describing one holding register.
- **Read_Block**: A contiguous group of register addresses read in one FC03 `read_holding_registers` request, containing at most 100 registers.
- **Controller_Snapshot**: The domain entity representing one complete poll cycle of Controller register values, including raw values, scaled values, and error history, plus metadata (slave id, timestamp, read failures).
- **Controller_Snapshot_Repository**: The domain port for persisting and querying Controller_Snapshot records.
- **Poll_Controller_Use_Case**: The application use case that orchestrates one Controller poll cycle: read, build snapshot, persist, enqueue, publish.
- **Mqtt_Publisher**: The existing infrastructure MQTT adapter publishing to `embody/w` and `embody/r`.
- **Flat_Payload**: A flat JSON object mapping each register's decimal address string to its raw register value, plus a `slave_id` field, published to `embody/elevator`.
- **Scale_Factor**: A string such as `/10` or `/100` describing how to convert a raw register value to a scaled engineering value.
- **Settings**: The project `pydantic_settings`-based configuration object that sources values from environment variables, `.env`, and `config/config.yaml`.
- **FC03**: Modbus function code 3, `read_holding_registers`.
- **Poll_Interval**: The configurable duration between full Controller poll cycles.

## Requirements

### Requirement 1: Read controller registers via pymodbus

**User Story:** As a system integrator, I want the controller's holding registers read through a `pymodbus`-based adapter behind a domain port, so that the proven script behavior runs inside Clean Architecture without coupling the application layer to `pymodbus`.

#### Acceptance Criteria

1. THE Controller_Gateway SHALL implement the Controller_Gateway_Port defined in the domain layer.
2. THE Controller_Gateway SHALL read Controller holding registers using a `pymodbus` `ModbusSerialClient`.
3. WHEN a poll cycle begins, THE Controller_Gateway SHALL read every Register_Entry defined in the Register_Map.
4. WHEN a poll cycle begins, THE Controller_Gateway SHALL issue Modbus FC03 read requests to the Controller at the slave id provided by Settings, where the slave id is an integer in the range 1 to 247 inclusive.
5. IF a Settings slave id is outside the range 1 to 247 inclusive, THEN THE Controller_Gateway SHALL reject the poll cycle and return an error result indicating an invalid slave id, without issuing any FC03 request.
6. WHILE awaiting an FC03 response, THE Controller_Gateway SHALL apply a per-request read timeout configured in Settings within the range 100 to 10000 milliseconds, defaulting to 1000 milliseconds when not specified.
7. IF an FC03 read request fails, times out, or returns a Modbus exception response for any Register_Entry, THEN THE Controller_Gateway SHALL return a failure result for the poll cycle that identifies the affected Register_Entry, and SHALL NOT return partial register values as successful readings.
8. IF the `ModbusSerialClient` connection to the Controller cannot be established, THEN THE Controller_Gateway SHALL return a failure result indicating the connection is unavailable, without issuing any FC03 request.
9. THE Controller_Gateway_Port SHALL NOT expose `pymodbus` types in the application layer.
10. THE domain layer SHALL NOT import `pymodbus`, `minimalmodbus`, application, infrastructure, or presentation modules.

### Requirement 2: Group registers into minimal read blocks

**User Story:** As a system integrator, I want contiguous registers grouped into the fewest FC03 requests, so that each poll cycle minimizes bus traffic while respecting Modbus limits.

#### Acceptance Criteria

1. WHEN building Read_Blocks, THE Controller_Gateway SHALL sort all Register_Entries in the Register_Map by register address in strictly ascending order before grouping.
2. WHEN the next Register_Entry address equals the highest address currently in the active Read_Block plus 1 AND the active Read_Block contains 99 or fewer registers, THE Controller_Gateway SHALL add that Register_Entry to the active Read_Block.
3. IF the next Register_Entry address is greater than the highest address currently in the active Read_Block plus 1, THEN THE Controller_Gateway SHALL close the active Read_Block and begin a new Read_Block starting at that Register_Entry.
4. IF the active Read_Block already contains exactly 100 registers, THEN THE Controller_Gateway SHALL close the active Read_Block and begin a new Read_Block starting at the next Register_Entry, regardless of contiguity.
5. THE Controller_Gateway SHALL ensure that no Read_Block contains more than 100 registers and that no Read_Block contains an address gap between any two consecutive registers.
6. WHEN a Read_Block has been read and at least one additional Read_Block remains to be read in the same poll cycle, THE Controller_Gateway SHALL wait 0.05 seconds (50 milliseconds), within a tolerance of plus or minus 5 milliseconds, before issuing the next read request.
7. WHEN all Read_Blocks for a poll cycle have been read, THE Controller_Gateway SHALL include the value of every Register_Entry in the Register_Map exactly once in the resulting snapshot.
8. IF the Register_Map contains zero Register_Entries, THEN THE Controller_Gateway SHALL produce zero Read_Blocks and return an empty snapshot without issuing any read request.

### Requirement 3: Build a controller snapshot with raw and scaled values

**User Story:** As a data consumer, I want each poll cycle captured as a controller snapshot with raw and scaled values, so that downstream persistence, queuing, publishing, and inference share a consistent structure.

#### Acceptance Criteria

1. WHEN a poll cycle completes, THE Poll_Controller_Use_Case SHALL produce exactly one Controller_Snapshot, regardless of whether all, some, or none of the Register_Entry reads succeeded.
2. WHEN a poll cycle completes, THE Controller_Snapshot SHALL contain, for each successfully read Register_Entry, the raw value as an unsigned 16-bit integer in the range 0 to 65535 inclusive.
3. WHEN a poll cycle completes and a Register_Entry has a non-empty Scale_Factor, THE Poll_Controller_Use_Case SHALL parse the Scale_Factor string as a base-10 integer and set the scaled value to the exact decimal quotient of the raw value divided by that integer.
4. IF a Register_Entry has a non-empty Scale_Factor that does not parse as a base-10 integer, or parses to zero, THEN THE Poll_Controller_Use_Case SHALL set the scaled value equal to the raw value and record an indication that the Scale_Factor was invalid for that Register_Entry.
5. WHERE a Register_Entry has an empty Scale_Factor, THE Poll_Controller_Use_Case SHALL set the scaled value equal to the raw value.
6. WHEN a poll cycle completes, THE Controller_Snapshot SHALL include the Controller slave id.
7. WHEN a poll cycle completes, THE Controller_Snapshot SHALL include a timestamp identifying the poll cycle, expressed in UTC as an ISO-8601 string terminated with the "Z" designator.
8. WHEN a poll cycle completes, THE Controller_Snapshot SHALL include the six error-history blocks with their constituent register values.
9. IF reading a Register_Entry fails during the poll cycle, THEN THE Poll_Controller_Use_Case SHALL exclude that Register_Entry's raw and scaled values from the Controller_Snapshot and record an indication that the read for that Register_Entry failed.
10. THE Controller_Snapshot SHALL be defined as a domain entity such that the existing `SensorReading` entity requires no modification to accommodate it.

### Requirement 4: Persist controller snapshots

**User Story:** As an operator, I want each controller snapshot persisted to SQLite, so that history is queryable by the API and processing use cases.

#### Acceptance Criteria

1. THE Controller_Snapshot_Repository SHALL be defined as a domain port.
2. WHEN a Controller_Snapshot is produced, THE Poll_Controller_Use_Case SHALL persist the Controller_Snapshot through the Controller_Snapshot_Repository within 2 seconds of production.
3. WHEN a Controller_Snapshot is persisted, THE Controller_Snapshot_Repository SHALL store the raw register values for that snapshot.
4. WHEN a Controller_Snapshot is persisted, THE Controller_Snapshot_Repository SHALL store the scaled register values for that snapshot.
5. WHEN a Controller_Snapshot is persisted, THE Controller_Snapshot_Repository SHALL store all six error-history blocks for that snapshot.
6. THE Controller_Snapshot_Repository SHALL store Controller_Snapshot records in a database table that is separate from the existing `SensorReading` storage.
7. WHEN a Controller_Snapshot is queried by elevator id and one or more persisted snapshots exist for that elevator id, THE Controller_Snapshot_Repository SHALL return all persisted snapshots for that elevator id ordered from most recent timestamp to oldest timestamp.
8. FOR ALL Controller_Snapshot values, persisting a snapshot then reading the snapshot back SHALL produce equivalent raw values, scaled values, slave id, and timestamp (round-trip property).
9. IF persisting a Controller_Snapshot through the Controller_Snapshot_Repository fails, THEN THE Poll_Controller_Use_Case SHALL return an error indication identifying the failed persistence operation and SHALL NOT store a partial Controller_Snapshot record.
10. WHEN a Controller_Snapshot is queried by elevator id and no persisted snapshots exist for that elevator id, THE Controller_Snapshot_Repository SHALL return an empty result without raising an error.

### Requirement 5: Publish flat payload to embody/elevator

**User Story:** As a cloud consumer, I want the controller snapshot published as a flat JSON payload to `embody/elevator`, so that the proven downstream contract from the tested script is preserved.

#### Acceptance Criteria

1. WHEN a Controller_Snapshot is produced, THE Poll_Controller_Use_Case SHALL publish a Flat_Payload to MQTT topic `embody/elevator` within 5 seconds of the Controller_Snapshot being produced.
2. THE Flat_Payload SHALL map each successfully read register's decimal address, represented as a base-10 string, to that register's raw 16-bit unsigned integer value in the range 0 to 65535.
3. THE Flat_Payload SHALL include a `slave_id` field set to the Controller slave id as an integer in the range 1 to 247.
4. THE Poll_Controller_Use_Case SHALL publish the Flat_Payload with MQTT QoS 1.
5. FOR ALL Controller_Snapshot register values, serializing the Flat_Payload to JSON then deserializing SHALL produce equivalent address-to-raw-value entries (round-trip property).
6. IF the MQTT publish fails or does not complete within 5 seconds, THEN THE Poll_Controller_Use_Case SHALL log an entry indicating the publish failure and SHALL continue the current poll cycle without raising an unhandled exception, retaining the Controller_Snapshot unchanged.
7. WHEN a Controller_Snapshot contains zero successfully read registers, THE Poll_Controller_Use_Case SHALL publish a Flat_Payload containing only the `slave_id` field to MQTT topic `embody/elevator`.

### Requirement 6: Preserve existing MQTT topics and sensor reads

**User Story:** As a maintainer, I want existing behavior preserved, so that adding controller telemetry does not break field-sensor reads or the current MQTT contract.

#### Acceptance Criteria

1. THE feature SHALL retain the existing `ModbusGateway` `minimalmodbus` reads for the `ES-VS-01`, `ES35-SW`, and `RW-ST01D` sensors with identical read behavior, register addressing, and normalized `SensorReading` output as before this feature.
2. THE feature SHALL retain MQTT publishing to topics `embody/w` and `embody/r` with the same payload structure and content as before this feature.
3. WHERE the existing poll cycle publishes to `embody/w` and `embody/r`, THE feature SHALL continue to publish to those two topics within the same poll cycle, in addition to publishing the Flat_Payload to `embody/elevator`.
4. IF the Controller poll fails, THEN THE Poll_Controller_Use_Case SHALL log the failure and SHALL allow the existing field-sensor poll cycle to complete its read, persist, enqueue, and publish steps without interruption.
5. IF the Controller poll raises an exception, THEN THE feature SHALL contain the exception within the Controller poll path and SHALL NOT propagate an unhandled exception into the existing field-sensor poll cycle.

### Requirement 7: Enqueue snapshots for downstream processing

**User Story:** As a processing-pipeline owner, I want controller snapshots enqueued, so that the existing queue-driven processing flow can consume controller telemetry.

#### Acceptance Criteria

1. WHEN a Controller_Snapshot is persisted, THE Poll_Controller_Use_Case SHALL enqueue exactly one serialized representation of that Controller_Snapshot to the reading queue.
2. THE enqueued representation SHALL include the raw register values, scaled register values, slave id, timestamp, and read-failure list of the Controller_Snapshot.
3. THE enqueued representation SHALL be a JSON-serializable object.
4. FOR ALL Controller_Snapshot values, serializing the enqueued representation to JSON then deserializing SHALL produce equivalent raw values, scaled values, slave id, timestamp, and read-failure entries (round-trip property).
5. IF enqueuing fails, THEN THE Poll_Controller_Use_Case SHALL log the failure, retain the already persisted Controller_Snapshot, and continue the poll cycle without raising an unhandled exception.

### Requirement 8: Configuration and credentials from Settings

**User Story:** As a security-conscious operator, I want all serial settings, MQTT settings, register map, and credentials sourced from Settings/environment, so that no secrets or connection values are hardcoded in adapter code.

#### Acceptance Criteria

1. THE Controller_Gateway SHALL obtain the serial port, baud rate, parity, data bits, stop bits, and timeout from Settings.
2. THE Controller_Gateway SHALL obtain the Controller slave id from Settings.
3. THE Poll_Controller_Use_Case SHALL obtain the Poll_Interval from Settings.
4. THE Mqtt_Publisher SHALL obtain the broker host, port, username, password, and client id from Settings.
5. THE feature SHALL obtain the `embody/elevator` topic name from Settings.
6. THE feature SHALL NOT contain hardcoded MQTT credentials, broker addresses, or serial port values in source code.
7. WHERE Settings provides the Register_Map or register definitions, THE Controller_Gateway SHALL read register addresses, scale factors, and display bases from Settings rather than from inline literals in adapter logic.

### Requirement 9: Polling cadence

**User Story:** As an operator, I want the controller polled on a configurable interval, so that telemetry freshness matches operational needs.

#### Acceptance Criteria

1. THE Poll_Controller_Use_Case SHALL support repeated poll cycles separated by the Poll_Interval.
2. WHERE no Poll_Interval is configured, THE Poll_Controller_Use_Case SHALL default to 5 seconds.
3. WHEN a poll cycle completes, THE Poll_Controller_Use_Case SHALL wait the Poll_Interval before beginning the next poll cycle.

### Requirement 10: Error handling for register reads

**User Story:** As an operator, I want individual block read failures handled gracefully, so that a partial bus fault does not abort the entire poll cycle.

#### Acceptance Criteria

1. IF a Read_Block read returns a Modbus error, THEN THE Controller_Gateway SHALL record the affected register addresses as read failures and continue with the remaining Read_Blocks.
2. IF a Read_Block read raises a Modbus exception, THEN THE Controller_Gateway SHALL record the affected register addresses as read failures and continue with the remaining Read_Blocks.
3. WHEN at least one register is read successfully, THE Poll_Controller_Use_Case SHALL produce a Controller_Snapshot containing the successfully read registers.
4. IF no registers are read successfully in a poll cycle, THEN THE Poll_Controller_Use_Case SHALL log a warning and skip persistence, enqueuing, and publishing for that poll cycle.
5. THE Controller_Snapshot SHALL include the list of register addresses that failed to read during the poll cycle.

### Requirement 11: Expose controller telemetry via API

**User Story:** As a frontend developer, I want controller snapshots available through the DB-driven API, so that the React frontend can display controller telemetry over REST and WebSocket without consuming MQTT directly.

#### Acceptance Criteria

1. WHEN a client requests controller snapshot history for an elevator id, THE presentation API SHALL return persisted Controller_Snapshot records for that elevator id.
2. WHERE query filters for time range are provided, THE presentation API SHALL return only Controller_Snapshot records within the requested time range.
3. THE presentation API SHALL source Controller_Snapshot data from the Controller_Snapshot_Repository rather than from MQTT.
