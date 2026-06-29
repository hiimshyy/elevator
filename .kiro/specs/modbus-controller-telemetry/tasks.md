# Implementation Plan: Modbus Controller Telemetry

## Overview

This plan converts the controller-telemetry design into incremental coding steps for the
Python Clean Architecture system in `src/elevator_pdm/`. Work flows inward-out: domain
value objects, entities, and ports first; then configuration; then the pure read-block
planner; then the `pymodbus` gateway adapter; then the `PollControllerUseCase`
orchestration; then SQLite persistence, MQTT publishing, and the REST router; and finally
wiring the controller poll path into a guarded runner alongside the existing field-sensor
cycle. Each step builds on the previous one and ends fully integrated — no orphaned code.

Property-based tests use **Hypothesis** (added to `[dev]` extras) and follow the design's
property-to-test mapping. Each property test runs at least 100 examples and is tagged
`# Feature: modbus-controller-telemetry, Property {N}: {text}`.

## Tasks

- [x] 1. Define domain value objects, entity, and ports for controller telemetry
  - [x] 1.1 Create register-map value objects
    - In `src/elevator_pdm/domain/value_objects/register_map.py`, add frozen dataclasses `RegisterEntry` (address, key, meaning, base, scale, unit), `RegisterMap` (entries tuple), `ReadBlock` (start, count, entries), and `RegisterValue` (address, raw, scaled, scale_invalid)
    - Export them from `domain/value_objects/__init__.py`
    - _Requirements: 2.5, 3.2, 3.4_

  - [x] 1.2 Create the `ControllerSnapshot` domain entity
    - In `src/elevator_pdm/domain/entities/controller_snapshot.py`, add frozen dataclasses `ErrorBlock` (index, values) and `ControllerSnapshot` (elevator_id, slave_id, timestamp, raw_values, scaled_values, error_blocks, failed_addresses, id)
    - Mirror the existing `sensor_reading.py` frozen-dataclass style; do not modify `SensorReading`
    - Export from `domain/entities/__init__.py`
    - _Requirements: 3.1, 3.6, 3.7, 3.8, 3.10_

  - [x] 1.3 Create the `ControllerGatewayPort` port and read-result types
    - In `src/elevator_pdm/domain/interfaces/controller_gateway.py`, add an `abc.ABC` port `ControllerGatewayPort` with abstract `read_snapshot() -> ControllerReadResult`, plus a `ControllerReadStatus` enum (`OK`, `INVALID_SLAVE_ID`, `CONNECTION_UNAVAILABLE`) and frozen `ControllerReadResult` (status, slave_id, raw_values, failed_addresses)
    - Expose only domain types; import no `pymodbus`/`minimalmodbus` or outward modules
    - _Requirements: 1.1, 1.9, 1.10_

  - [x] 1.4 Create the `ControllerSnapshotRepository` port
    - In `src/elevator_pdm/domain/interfaces/controller_snapshot_repository.py`, add an `abc.ABC` with `save(snapshot)`, `find_by_elevator(elevator_id, from_ts, to_ts, limit)`, and `find_latest(elevator_id)`
    - Mirror the existing `reading_repository.py` port style
    - _Requirements: 4.1, 4.7, 4.10_

  - [x] 1.5 Extend the `MqttPublisher` domain protocol
    - In `src/elevator_pdm/domain/interfaces/mqtt_publisher.py`, add `publish_controller_snapshot(payload: dict[str, Any]) -> bool` to the existing `Protocol` without altering the existing `publish_reading`/`publish_status` signatures
    - _Requirements: 5.1, 6.2_

  - [x] 1.6 Write smoke test for domain isolation
    - In `tests/unit/domain/test_controller_imports.py`, assert the new domain modules import no `pymodbus`, `minimalmodbus`, application, infrastructure, or presentation modules
    - _Requirements: 1.10, 3.10_

- [x] 2. Add configuration and test dependency
  - [x] 2.1 Add controller telemetry settings and config defaults
    - In `src/elevator_pdm/infrastructure/config/settings.py`, add `ControllerSerialConfig`, `RegisterEntryConfig`, and `ControllerTelemetryConfig` `BaseModel` groups and mount `controller_telemetry` on the `Settings` root; seed the register map from the `test_modbus.py` map
    - Mirror the defaults in `config/config.yaml`; keep the legacy `controller` block unchanged and source MQTT broker/credentials from the existing `mqtt` config
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 9.2_

  - [x] 2.2 Add Hypothesis to dev dependencies
    - Add `hypothesis` to the `[dev]` extras in `pyproject.toml`
    - _Requirements: 4.8_

  - [x] 2.3 Write config-sourcing smoke test
    - In `tests/unit/infrastructure/test_settings_controller.py`, assert serial profile, slave id, poll interval, topic, and register map load from `Settings`, and scan adapter sources for absence of hardcoded credentials/addresses/ports
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

- [x] 3. Implement the pure read-block planner and scaling helpers
  - [x] 3.1 Implement `build_read_blocks` and `apply_scale`
    - In `src/elevator_pdm/application/services/read_block_planner.py`, implement side-effect-free `build_read_blocks(register_map) -> list[ReadBlock]` (sort ascending, extend on contiguity when block ≤ 99, split on gap or at 100, empty map → no blocks) and `apply_scale(raw, scale) -> RegisterValue`-style result (parse `/N` base-10 divisor; raw + invalid flag on non-integer/zero; raw on empty)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.8, 3.3, 3.4, 3.5_

  - [x] 3.2 Write property test for read-block coverage
    - In `tests/unit/application/test_read_block_planner.py`
    - **Property 1: Read-block planning covers every register exactly once**
    - **Validates: Requirements 1.3, 2.7**

  - [x] 3.3 Write property test for block size and contiguity invariants
    - In `tests/unit/application/test_read_block_planner.py`
    - **Property 2: Read blocks respect size and contiguity invariants**
    - **Validates: Requirements 2.2, 2.3, 2.4, 2.5, 2.8**

  - [x] 3.4 Write property test for global ascending order
    - In `tests/unit/application/test_read_block_planner.py`
    - **Property 3: Read blocks are globally ascending**
    - **Validates: Requirements 2.1**

  - [x] 3.5 Write property test for scale application
    - In `tests/unit/application/test_read_block_planner.py`
    - **Property 6: Scale application is correct across all scale strings**
    - **Validates: Requirements 3.3, 3.4, 3.5**

- [x] 4. Implement the pymodbus controller gateway adapter
  - [x] 4.1 Implement `PymodbusControllerGateway`
    - In `src/elevator_pdm/infrastructure/sensors/pymodbus_controller_gateway.py`, implement `ControllerGatewayPort` using `ModbusSerialClient` built from `Settings.controller_telemetry`; add a timeout-clamp helper (default 1000 ms, clamp to [100, 10000]); validate slave id ∈ [1, 247] before I/O; call `build_read_blocks`; issue FC03 per block; record block addresses as failures on `isError()`/`ModbusException` and continue; sleep 50 ms between remaining blocks; never let `pymodbus` exceptions cross the port
    - _Requirements: 1.2, 1.4, 1.5, 1.6, 1.7, 1.8, 2.6, 3.2, 10.1, 10.2_

  - [x] 4.2 Write property test for slave-id validation gating
    - In `tests/unit/infrastructure/test_pymodbus_controller_gateway.py` with a mocked client
    - **Property 4: Slave id validation gates the poll cycle**
    - **Validates: Requirements 1.4, 1.5**

  - [x] 4.3 Write property test for timeout clamping
    - In `tests/unit/infrastructure/test_pymodbus_controller_gateway.py`
    - **Property 5: Per-request timeout is clamped with default**
    - **Validates: Requirements 1.6**

  - [x] 4.4 Write example tests for gateway branches
    - In `tests/unit/infrastructure/test_pymodbus_controller_gateway.py`, cover the connection-unavailable path, block error/exception → failure recording, and that the inter-block 50 ms sleep is invoked `n-1` times via a sleep spy
    - _Requirements: 1.7, 1.8, 2.6, 10.1, 10.2_

- [x] 5. Implement the controller poll use case
  - [x] 5.1 Implement snapshot building, flat payload, and enqueue serializer
    - In `src/elevator_pdm/application/use_cases/poll_controller.py`, implement `PollControllerUseCase.__init__` (gateway, repo, queue, mqtt, settings) and the pure helpers that build a `ControllerSnapshot` from a `ControllerReadResult` (scaled values via `apply_scale`, slave id, UTC ISO-8601 `Z` timestamp, six error blocks, failed addresses), build the flat `embody/elevator` payload, and serialize the enqueue representation
    - _Requirements: 3.1, 3.2, 3.6, 3.7, 3.8, 3.9, 5.2, 5.3, 7.2, 7.3_

  - [x] 5.2 Implement `execute` and `run_forever` orchestration
    - In the same module, implement `execute(elevator_id)` (hard-fail on non-OK status; on zero registers log warning, skip persist/enqueue, publish slave_id-only payload; otherwise persist within 2 s, enqueue once, publish flat payload at QoS 1; independent try/except so publish/enqueue failures are logged and tolerated) and `run_forever` honoring the poll interval (default 5 s), guarded so controller failures never propagate
    - _Requirements: 4.2, 4.9, 5.1, 5.4, 5.6, 5.7, 6.4, 6.5, 7.1, 7.5, 9.1, 9.2, 9.3, 10.3, 10.4_

  - [x] 5.3 Write property test for snapshot construction
    - In `tests/unit/application/test_poll_controller.py`
    - **Property 7: Snapshot construction produces a complete, well-formed snapshot**
    - **Validates: Requirements 3.1, 3.2, 3.6, 3.7, 3.8**

  - [x] 5.4 Write property test for success/failure partition
    - In `tests/unit/application/test_poll_controller.py`
    - **Property 8: Successful and failed addresses form a complete disjoint partition**
    - **Validates: Requirements 3.9, 10.1, 10.2, 10.3, 10.5**

  - [x] 5.5 Write property test for flat payload mapping and round-trip
    - In `tests/unit/application/test_poll_controller.py`
    - **Property 11: Flat payload mapping and JSON round-trip**
    - **Validates: Requirements 5.2, 5.3, 5.5**

  - [x] 5.6 Write property test for enqueue round-trip and single enqueue
    - In `tests/unit/application/test_poll_controller.py`
    - **Property 12: Enqueued representation round-trips and is enqueued once**
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4**

  - [x] 5.7 Write property test for controller-poll failure containment
    - In `tests/unit/application/test_poll_controller.py`
    - **Property 13: Controller poll failures are contained**
    - **Validates: Requirements 6.4, 6.5**

  - [x] 5.8 Write property test for poll-interval default
    - In `tests/unit/application/test_poll_controller.py`
    - **Property 14: Poll interval defaults when unconfigured**
    - **Validates: Requirements 9.2**

  - [x] 5.9 Write example tests for use-case branches
    - In `tests/unit/application/test_poll_controller.py`, cover persist-within-2s, zero-register cycle (skip persist/enqueue, publish slave_id-only), tolerated publish failure, tolerated enqueue failure, QoS 1 usage, and repeated cycles honoring the interval with patched sleep
    - _Requirements: 4.2, 5.4, 5.6, 5.7, 7.5, 9.1, 9.3, 10.4_

- [x] 6. Checkpoint - core read/transform/orchestrate path
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Implement controller snapshot persistence
  - [x] 7.1 Add the controller snapshot ORM model and table creation
    - In `src/elevator_pdm/infrastructure/persistence/models.py`, add a `ControllerSnapshotRow` model (separate `controller_snapshots` table) with first-class `elevator_id`, `slave_id`, `timestamp`, `synced` columns, JSON `Text` columns for raw/scaled/error-blocks/failed-addresses, and an `(elevator_id, timestamp)` index; ensure it is created via the shared `Base.metadata.create_all` in `database.py`
    - _Requirements: 4.3, 4.4, 4.5, 4.6_

  - [x] 7.2 Implement `SQLiteControllerSnapshotRepo`
    - In `src/elevator_pdm/infrastructure/persistence/sqlite_controller_snapshot_repo.py`, implement the repository port with `_to_orm`/`_to_domain` conversions; `find_by_elevator` orders by timestamp descending with time-range filters and capped limit; `find_latest` returns the newest or `None`; persistence failures surface without writing a partial row
    - _Requirements: 4.2, 4.7, 4.9, 4.10_

  - [x] 7.3 Write property test for persistence round-trip
    - In `tests/integration/persistence/test_controller_snapshot_repo.py` using in-memory SQLite
    - **Property 9: Persistence round-trip preserves snapshot data**
    - **Validates: Requirements 4.3, 4.4, 4.5, 4.8**

  - [x] 7.4 Write property test for newest-first ordering
    - In `tests/integration/persistence/test_controller_snapshot_repo.py`
    - **Property 10: Snapshot queries return newest-first**
    - **Validates: Requirements 4.7**

  - [ ]* 7.5 Write edge tests for the repository
    - In `tests/integration/persistence/test_controller_snapshot_repo.py`, cover query with no rows returns `[]` and persist failure writes no partial row
    - _Requirements: 4.9, 4.10_

- [x] 8. Implement the MQTT flat-payload publisher
  - [x] 8.1 Add `publish_controller_snapshot` to the MQTT adapter
    - In `src/elevator_pdm/infrastructure/messaging/mqtt_publisher.py`, add `publish_controller_snapshot` that publishes the flat payload to the `embody/elevator` topic (from `Settings`) at QoS 1, reusing existing connection management, pending-queue, and `wait_for_publish`; return `bool` and treat `False`/timeout as non-fatal
    - _Requirements: 5.1, 5.4, 5.6, 8.5_

- [x] 9. Expose controller telemetry over REST
  - [x] 9.1 Add the `ControllerSnapshotResponse` schema
    - In `src/elevator_pdm/presentation/api/schemas/responses.py`, add a Pydantic response model with slave id, timestamp, raw values, scaled values, error-history blocks, and failed addresses
    - _Requirements: 11.1_

  - [x] 9.2 Add the controller router and dependency wiring
    - Create `src/elevator_pdm/presentation/api/routers/controller.py` exposing `GET /elevators/{elevator_id}/controller-snapshots` (newest first, `from_time`/`to_time` filters, capped limit) sourced from `ControllerSnapshotRepository`; add a `get_controller_snapshot_repository` dependency in `dependencies.py` and register the router in `main.py`
    - _Requirements: 11.1, 11.2, 11.3_

  - [x] 9.3 Write integration tests for the controller router
    - In `tests/integration/api/test_controller_router.py`, assert the endpoint returns persisted snapshots newest-first, applies time-range filtering, and sources data from the repository (not MQTT)
    - _Requirements: 11.1, 11.2, 11.3_

- [x] 10. Wire the controller poll path into a guarded runner
  - [x] 10.1 Add the controller poll runner script
    - Create `scripts/poll_controller_pipeline.py` that constructs `PymodbusControllerGateway`, `SQLiteControllerSnapshotRepo`, the reading queue, and the MQTT publisher from `Settings` and drives `PollControllerUseCase`, invoked in a guarded block fully separate from `PollSensorsUseCase` so it cannot interrupt the field-sensor cycle
    - _Requirements: 6.3, 6.4, 6.5, 9.1, 9.3_

  - [x] 10.2 Write integration test for the combined poll cycle
    - In `tests/integration/test_combined_poll_cycle.py`, with mocked Modbus/MQTT clients assert one combined cycle publishes to `embody/w`, `embody/r`, and `embody/elevator`, and that a controller-poll failure leaves the field-sensor cycle intact
    - _Requirements: 6.3, 6.4, 6.5_

  - [x] 10.3 Write regression smoke tests
    - Confirm existing `ModbusGateway`/`SensorReading` and `embody/w`/`embody/r` tests remain green and unchanged
    - _Requirements: 6.1, 6.2_

- [x] 11. Final checkpoint - full feature
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional test sub-tasks and can be skipped for a faster MVP.
- Each task references specific requirement sub-clauses for traceability.
- Property tests implement the design's Correctness Properties (one test per property, ≥100 Hypothesis examples, tagged with the property number).
- The existing `minimalmodbus` `ModbusGateway`, `SensorReading`, and `embody/w`/`embody/r` flows are left untouched; controller telemetry is purely additive.
- Checkpoints provide incremental validation points before persistence/API/wiring work.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3", "1.4", "1.5", "2.1", "2.2"] },
    { "id": 1, "tasks": ["1.6", "2.3", "3.1", "4.1", "7.1", "8.1", "9.1"] },
    { "id": 2, "tasks": ["3.2", "4.2", "5.1", "7.2", "9.2"] },
    { "id": 3, "tasks": ["3.3", "4.3", "5.2", "7.3", "9.3"] },
    { "id": 4, "tasks": ["3.4", "4.4", "5.3", "7.4", "10.1"] },
    { "id": 5, "tasks": ["3.5", "5.4", "7.5", "10.2"] },
    { "id": 6, "tasks": ["5.5", "10.3"] },
    { "id": 7, "tasks": ["5.6"] },
    { "id": 8, "tasks": ["5.7"] },
    { "id": 9, "tasks": ["5.8"] },
    { "id": 10, "tasks": ["5.9"] }
  ]
}
```
