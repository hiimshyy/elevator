"""Property-based tests for PollControllerUseCase snapshot construction.

Tests target the pure snapshot-building logic exposed via ``build_snapshot``
and the full ``PollControllerUseCase.execute`` path with mocked I/O dependencies.
"""
from __future__ import annotations

from unittest.mock import MagicMock, call

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import json

from elevator_pdm.application.use_cases.poll_controller import (
    PollControllerUseCase,
    build_elevator_payload,
    build_enqueue_payload,
    build_snapshot,
)
from elevator_pdm.domain.interfaces.controller_gateway import (
    ControllerReadResult,
    ControllerReadStatus,
)
from elevator_pdm.infrastructure.config.settings import (
    ControllerTelemetryConfig,
    RegisterEntryConfig,
    Settings,
)

# ---------------------------------------------------------------------------
# Hypothesis strategy for disjoint attempted-address sets
# ---------------------------------------------------------------------------

# Strategy that produces (raw_values, failed_addresses, all_attempted_addresses)
# where raw_values keys and failed_addresses are disjoint and together equal
# all_attempted_addresses — mirroring what the real gateway produces.
_address_pool_st = st.lists(
    st.integers(min_value=0, max_value=65535),
    min_size=0,
    max_size=60,
    unique=True,
)


@st.composite
def _partition_st(draw: st.DrawFn) -> tuple[dict[int, int], tuple[int, ...], frozenset[int]]:
    """Draw a pool of unique addresses and split them into success / failure sets."""
    pool: list[int] = draw(_address_pool_st)
    if not pool:
        return {}, (), frozenset()

    # For each address decide: success (True) or failure (False)
    outcomes: list[bool] = draw(
        st.lists(st.booleans(), min_size=len(pool), max_size=len(pool))
    )

    raw_values: dict[int, int] = {}
    failed: list[int] = []
    for addr, success in zip(pool, outcomes):
        if success:
            raw_values[addr] = draw(st.integers(min_value=0, max_value=65535))
        else:
            failed.append(addr)

    return raw_values, tuple(failed), frozenset(pool)

# ---------------------------------------------------------------------------
# Constants matching the implementation's error-block layout
# (mirrors _ERROR_OFFSETS and the base-address formula in poll_controller.py)
# ---------------------------------------------------------------------------

_ERROR_OFFSETS: tuple[int, ...] = (
    0x00,
    0x01,
    0x02,
    0x03,
    0x04,
    0x05,
    0x06,
    0x07,
    0x0E,
    0x0F,
    0x10,
    0x11,
    0x12,
    0x13,
)

_ERROR_BLOCK_BASE_ADDRESSES: tuple[int, ...] = tuple(
    0x3002 + (n - 1) * 0x20 for n in range(1, 7)
)

# All addresses that belong to any error block
_ALL_ERROR_BLOCK_ADDRESSES: frozenset[int] = frozenset(
    base + offset for base in _ERROR_BLOCK_BASE_ADDRESSES for offset in _ERROR_OFFSETS
)


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# slave_id: valid range 1..247 per R1.4
_slave_id_st = st.integers(min_value=1, max_value=247)

# elevator_id: non-empty short strings
_elevator_id_st = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"),
    min_size=1,
    max_size=20,
)

# raw_values dict: address -> 16-bit unsigned integer
_raw_values_st = st.dictionaries(
    keys=st.integers(min_value=0, max_value=65535),
    values=st.integers(min_value=0, max_value=65535),
    min_size=0,
    max_size=50,
)

# Register entry: address, optional scale, matches RegisterEntryConfig
_register_entry_st = st.builds(
    RegisterEntryConfig,
    address=st.integers(min_value=0, max_value=65535),
    key=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_"),
        min_size=1,
        max_size=20,
    ),
    meaning=st.just(""),
    base=st.just(10),
    scale=st.one_of(
        st.just(""),
        st.builds(lambda n: f"/{n}", st.integers(min_value=1, max_value=1000)),
    ),
    unit=st.just(""),
)

# A small list of RegisterEntryConfig objects (may include duplicates by address;
# build_snapshot handles that gracefully via dict overwrite)
_register_map_st = st.lists(_register_entry_st, min_size=0, max_size=30)


def _make_settings(register_map: list[RegisterEntryConfig]) -> Settings:
    """Build a minimal Settings instance with the provided register map."""
    telemetry_cfg = ControllerTelemetryConfig(register_map=register_map)
    return Settings(controller_telemetry=telemetry_cfg)


def _make_mock_use_case(
    slave_id: int,
    raw_values: dict[int, int],
    register_map: list[RegisterEntryConfig],
) -> PollControllerUseCase:
    """Wire a PollControllerUseCase with mocked I/O returning the given read result."""
    read_result = ControllerReadResult(
        status=ControllerReadStatus.OK,
        slave_id=slave_id,
        raw_values=dict(raw_values),
        failed_addresses=(),
    )

    mock_gateway = MagicMock()
    mock_gateway.read_snapshot.return_value = read_result

    mock_repo = MagicMock()
    mock_repo.save.return_value = None

    mock_queue = MagicMock()
    mock_queue.enqueue.return_value = None

    mock_mqtt = MagicMock()
    mock_mqtt.publish_controller_snapshot.return_value = True

    settings_obj = _make_settings(register_map)

    return PollControllerUseCase(
        controller_gateway=mock_gateway,
        snapshot_repo=mock_repo,
        reading_queue=mock_queue,
        mqtt_publisher=mock_mqtt,
        settings=settings_obj,
    )


# ---------------------------------------------------------------------------
# Property 7: Snapshot construction produces a complete, well-formed snapshot
# ---------------------------------------------------------------------------

# Feature: modbus-controller-telemetry, Property 7: Snapshot construction
# produces a complete, well-formed snapshot
@given(
    slave_id=_slave_id_st,
    raw_values=_raw_values_st,
    elevator_id=_elevator_id_st,
    register_map=_register_map_st,
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_snapshot_construction_produces_well_formed_snapshot(
    slave_id: int,
    raw_values: dict[int, int],
    elevator_id: str,
    register_map: list[RegisterEntryConfig],
) -> None:
    """PollControllerUseCase produces exactly one well-formed ControllerSnapshot per poll cycle.

    Checks:
    - Exactly one snapshot per poll cycle (Req 3.1)
    - Every raw value is an unsigned 16-bit integer in 0..65535 (Req 3.2)
    - slave_id in the snapshot matches the read result (Req 3.6)
    - timestamp is a UTC ISO-8601 string ending with "Z" (Req 3.7)
    - exactly six error-history blocks are present (Req 3.8)

    Validates: Requirements 3.1, 3.2, 3.6, 3.7, 3.8
    """
    use_case = _make_mock_use_case(slave_id, raw_values, register_map)

    # Req 3.1: exactly one snapshot is produced per execute() call
    result = use_case.execute(elevator_id)

    # execute() must always return a PollControllerResult (not raise)
    assert result is not None

    # When raw_values is non-empty, execute() persists and returns a snapshot.
    # When raw_values is empty, execute() still returns a snapshot (skip-path).
    assert result.snapshot is not None, (
        "execute() must always produce a snapshot even for zero-register cycles"
    )

    snapshot = result.snapshot

    # Req 3.6: slave_id matches the read result
    assert snapshot.slave_id == slave_id

    # Req 3.7: timestamp is UTC ISO-8601 ending with "Z"
    assert isinstance(snapshot.timestamp, str)
    assert snapshot.timestamp.endswith("Z"), (
        f"timestamp must end with 'Z', got: {snapshot.timestamp!r}"
    )
    # Basic ISO-8601 structure: at minimum YYYY-MM-DDTHH:MM:SS...Z
    assert "T" in snapshot.timestamp, (
        f"timestamp must contain 'T' separator, got: {snapshot.timestamp!r}"
    )

    # Req 3.8: exactly six error-history blocks are present
    assert len(snapshot.error_blocks) == 6, (
        f"Expected 6 error blocks, got {len(snapshot.error_blocks)}"
    )
    # Blocks must be indexed 1 through 6
    block_indices = tuple(b.index for b in snapshot.error_blocks)
    assert block_indices == (1, 2, 3, 4, 5, 6), (
        f"Error block indices must be (1,2,3,4,5,6), got {block_indices}"
    )

    # Req 3.2: every raw value stored in the snapshot is in 0..65535
    for addr, raw in snapshot.raw_values.items():
        assert 0 <= raw <= 65535, (
            f"Raw value at address {addr} is out of 16-bit range: {raw}"
        )

    # Req 3.1 (structural): result holds exactly one snapshot reference
    assert result.snapshot is snapshot


# ---------------------------------------------------------------------------
# Direct pure-function test for build_snapshot (Property 7 via pure path)
# ---------------------------------------------------------------------------

# Feature: modbus-controller-telemetry, Property 7: Snapshot construction
# produces a complete, well-formed snapshot
@given(
    slave_id=_slave_id_st,
    raw_values=_raw_values_st,
    elevator_id=_elevator_id_st,
    register_map=_register_map_st,
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_build_snapshot_produces_well_formed_snapshot(
    slave_id: int,
    raw_values: dict[int, int],
    elevator_id: str,
    register_map: list[RegisterEntryConfig],
) -> None:
    """build_snapshot pure function produces a complete, well-formed ControllerSnapshot.

    This exercises the pure snapshot-building logic directly, independent of
    use-case I/O wiring, providing fast, focused coverage of Property 7.

    Checks:
    - slave_id in snapshot matches the read result (Req 3.6)
    - timestamp is UTC ISO-8601 ending with "Z" (Req 3.7)
    - exactly six error-history blocks are present, indexed 1..6 (Req 3.8)
    - every raw value in the snapshot is in 0..65535 (Req 3.2)

    Validates: Requirements 3.1, 3.2, 3.6, 3.7, 3.8
    """
    read_result = ControllerReadResult(
        status=ControllerReadStatus.OK,
        slave_id=slave_id,
        raw_values=dict(raw_values),
        failed_addresses=(),
    )

    snapshot = build_snapshot(read_result, elevator_id, register_map)

    # Req 3.6: slave_id matches
    assert snapshot.slave_id == slave_id

    # Req 3.7: timestamp ends with "Z" and contains "T"
    assert isinstance(snapshot.timestamp, str)
    assert snapshot.timestamp.endswith("Z")
    assert "T" in snapshot.timestamp

    # Req 3.8: exactly six error blocks, indexed 1..6
    assert len(snapshot.error_blocks) == 6
    assert tuple(b.index for b in snapshot.error_blocks) == (1, 2, 3, 4, 5, 6)

    # Req 3.2: all raw values are in 0..65535
    for addr, raw in snapshot.raw_values.items():
        assert 0 <= raw <= 65535, f"address {addr}: raw={raw} out of uint16 range"

    # elevator_id round-trips
    assert snapshot.elevator_id == elevator_id


# ---------------------------------------------------------------------------
# Property 8: Successful and failed addresses form a complete disjoint partition
# ---------------------------------------------------------------------------

# Feature: modbus-controller-telemetry, Property 8: Successful and failed
# addresses form a complete disjoint partition
@given(
    partition=_partition_st(),
    slave_id=_slave_id_st,
    elevator_id=_elevator_id_st,
    register_map=_register_map_st,
)
@settings(max_examples=150, suppress_health_check=[HealthCheck.too_slow])
def test_successful_and_failed_addresses_form_disjoint_partition(
    partition: tuple[dict[int, int], tuple[int, ...], frozenset[int]],
    slave_id: int,
    elevator_id: str,
    register_map: list[RegisterEntryConfig],
) -> None:
    """Successful reads and failed addresses are disjoint and together cover every attempted address.

    For any controller read result the following must hold:
    - The set of addresses present in the snapshot's raw_values is disjoint from
      failed_addresses  (Req 3.9, 10.5)
    - Their union equals the complete set of addresses attempted in the poll cycle
      (Req 10.1, 10.2, 10.3, 10.5)
    - A register whose block errored is excluded from raw/scaled values and
      recorded as failed — not silently dropped (Req 3.9)

    Validates: Requirements 3.9, 10.1, 10.2, 10.3, 10.5
    """
    raw_values, failed_addresses, all_attempted = partition

    read_result = ControllerReadResult(
        status=ControllerReadStatus.OK,
        slave_id=slave_id,
        raw_values=dict(raw_values),
        failed_addresses=failed_addresses,
    )

    snapshot = build_snapshot(read_result, elevator_id, register_map)

    successful_addresses: frozenset[int] = frozenset(snapshot.raw_values.keys())
    failed_set: frozenset[int] = frozenset(snapshot.failed_addresses)

    # --- Disjointness (Req 3.9, 10.5) ---
    overlap = successful_addresses & failed_set
    assert not overlap, (
        f"Addresses appear in both raw_values and failed_addresses: {overlap}"
    )

    # --- Completeness: union == all attempted (Req 10.1, 10.2, 10.3, 10.5) ---
    # build_snapshot receives raw_values and failed_addresses from the read result
    # and must not drop or invent addresses.
    assert successful_addresses == frozenset(raw_values.keys()), (
        "Snapshot raw_values keys must exactly match the successful addresses "
        "reported by the gateway"
    )
    assert failed_set == frozenset(failed_addresses), (
        "Snapshot failed_addresses must exactly match those reported by the gateway"
    )

    # Full partition check: success ∪ failure == all_attempted
    assert successful_addresses | failed_set == all_attempted, (
        f"Union of successful ({successful_addresses}) and failed ({failed_set}) "
        f"does not cover all attempted addresses ({all_attempted})"
    )

    # --- No silently dropped registers (Req 3.9) ---
    # Every address in all_attempted must appear in exactly one of the two sets.
    for addr in all_attempted:
        in_success = addr in successful_addresses
        in_failure = addr in failed_set
        assert in_success ^ in_failure, (
            f"Address {addr} must appear in exactly one partition set: "
            f"in_success={in_success}, in_failure={in_failure}"
        )


# ---------------------------------------------------------------------------
# Property 11: Flat payload mapping and JSON round-trip
# ---------------------------------------------------------------------------

# Feature: modbus-controller-telemetry, Property 11: Flat payload mapping and JSON round-trip
@given(
    slave_id=_slave_id_st,
    raw_values=_raw_values_st,
    elevator_id=_elevator_id_st,
    register_map=_register_map_st,
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_flat_payload_mapping_and_json_round_trip(
    slave_id: int,
    raw_values: dict[int, int],
    elevator_id: str,
    register_map: list,
) -> None:
    """build_elevator_payload produces a flat dict that maps each read register's
    decimal-address string to its raw 16-bit value, includes slave_id as int,
    and survives a JSON round-trip without data loss.

    Checks:
    - Req 5.2: Every address key is a base-10 string matching a raw_values address,
      with no extra or missing keys.
    - Req 5.3: payload["slave_id"] equals snapshot.slave_id and is an int.
    - Req 5.5: json.loads(json.dumps(payload)) preserves all entries.

    Validates: Requirements 5.2, 5.3, 5.5
    """
    read_result = ControllerReadResult(
        status=ControllerReadStatus.OK,
        slave_id=slave_id,
        raw_values=dict(raw_values),
        failed_addresses=(),
    )
    snapshot = build_snapshot(read_result, elevator_id, register_map)

    payload = build_elevator_payload(snapshot)

    # Req 5.3: slave_id is present, is an int, and matches the snapshot
    assert "slave_id" in payload
    assert isinstance(payload["slave_id"], int)
    assert payload["slave_id"] == slave_id

    # Req 5.2: all non-slave_id keys are decimal string representations of
    # addresses in snapshot.raw_values, and no extras appear
    address_keys = {k for k in payload if k != "slave_id"}
    expected_keys = {str(a) for a in snapshot.raw_values}
    assert address_keys == expected_keys, (
        f"Payload address keys {address_keys} do not match expected {expected_keys}"
    )

    # Req 5.2: each value equals the corresponding raw value
    for addr, raw in snapshot.raw_values.items():
        assert payload[str(addr)] == raw, (
            f"payload['{addr}'] = {payload[str(addr)]} != raw value {raw}"
        )

    # Edge case: empty raw_values → payload contains only slave_id
    if not snapshot.raw_values:
        assert set(payload.keys()) == {"slave_id"}

    # Req 5.5: JSON round-trip preserves all entries
    roundtripped = json.loads(json.dumps(payload))
    assert roundtripped["slave_id"] == payload["slave_id"]
    for k, v in payload.items():
        assert roundtripped[k] == v, (
            f"Round-trip mismatch at key '{k}': got {roundtripped[k]!r}, expected {v!r}"
        )


# ---------------------------------------------------------------------------
# Property 12: Enqueued representation round-trips and is enqueued once
# ---------------------------------------------------------------------------

# Strategies reused from above; we need raw_values with at least 1 entry so
# execute() takes the persist+enqueue path (not the zero-register skip path).
_nonempty_raw_values_st = st.dictionaries(
    keys=st.integers(min_value=0, max_value=65535),
    values=st.integers(min_value=0, max_value=65535),
    min_size=1,
    max_size=50,
)

# failed_addresses compatible with the register map: any tuple of ints
_failed_addresses_st = st.lists(
    st.integers(min_value=0, max_value=65535),
    min_size=0,
    max_size=20,
    unique=True,
).map(tuple)


# Feature: modbus-controller-telemetry, Property 12: Enqueued representation
# round-trips and is enqueued once
@given(
    slave_id=_slave_id_st,
    raw_values=_nonempty_raw_values_st,
    failed_addresses=_failed_addresses_st,
    elevator_id=_elevator_id_st,
    register_map=_register_map_st,
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_enqueue_payload_round_trips_and_is_enqueued_once(
    slave_id: int,
    raw_values: dict[int, int],
    failed_addresses: tuple[int, ...],
    elevator_id: str,
    register_map: list[RegisterEntryConfig],
) -> None:
    """Enqueued representation is JSON-serialisable, preserves all fields on round-trip,
    and execute() calls enqueue exactly once per successful poll cycle.

    Checks:
    - Req 7.1: exactly one call to queue.enqueue per successful cycle.
    - Req 7.2: the enqueued dict contains raw_values, scaled_values, slave_id,
               timestamp, and failed_addresses.
    - Req 7.3: the enqueued dict is JSON-serialisable (json.dumps does not raise).
    - Req 7.4: json.loads(json.dumps(payload)) round-trip preserves raw_values,
               scaled_values, slave_id, timestamp, and failed_addresses entries.

    Validates: Requirements 7.1, 7.2, 7.3, 7.4
    """
    # -----------------------------------------------------------------------
    # Part A: pure build_enqueue_payload function
    # -----------------------------------------------------------------------
    read_result = ControllerReadResult(
        status=ControllerReadStatus.OK,
        slave_id=slave_id,
        raw_values=dict(raw_values),
        failed_addresses=failed_addresses,
    )
    snapshot = build_snapshot(read_result, elevator_id, register_map)

    enqueue_dict = build_enqueue_payload(snapshot)

    # Req 7.2: required fields are present
    assert "raw_values" in enqueue_dict, "enqueue payload missing 'raw_values'"
    assert "scaled_values" in enqueue_dict, "enqueue payload missing 'scaled_values'"
    assert "slave_id" in enqueue_dict, "enqueue payload missing 'slave_id'"
    assert "timestamp" in enqueue_dict, "enqueue payload missing 'timestamp'"
    assert "failed_addresses" in enqueue_dict, "enqueue payload missing 'failed_addresses'"

    # Req 7.2: field types are correct
    assert isinstance(enqueue_dict["raw_values"], dict), (
        f"raw_values must be a dict, got {type(enqueue_dict['raw_values'])}"
    )
    assert isinstance(enqueue_dict["scaled_values"], dict), (
        f"scaled_values must be a dict, got {type(enqueue_dict['scaled_values'])}"
    )
    assert isinstance(enqueue_dict["slave_id"], int), (
        f"slave_id must be int, got {type(enqueue_dict['slave_id'])}"
    )
    assert isinstance(enqueue_dict["timestamp"], str), (
        f"timestamp must be str, got {type(enqueue_dict['timestamp'])}"
    )
    assert isinstance(enqueue_dict["failed_addresses"], list), (
        f"failed_addresses must be a list, got {type(enqueue_dict['failed_addresses'])}"
    )

    # Req 7.2: content correctness
    assert enqueue_dict["slave_id"] == slave_id, (
        f"slave_id mismatch: got {enqueue_dict['slave_id']}, expected {slave_id}"
    )
    assert enqueue_dict["timestamp"] == snapshot.timestamp, (
        f"timestamp mismatch: got {enqueue_dict['timestamp']!r}, "
        f"expected {snapshot.timestamp!r}"
    )
    # raw_values keys are decimal address strings, values are the raw ints
    for addr, raw in snapshot.raw_values.items():
        assert enqueue_dict["raw_values"][str(addr)] == raw, (
            f"raw_values['{addr}'] mismatch: "
            f"got {enqueue_dict['raw_values'].get(str(addr))}, expected {raw}"
        )
    # scaled_values keys match raw_values keys
    assert set(enqueue_dict["raw_values"].keys()) == set(enqueue_dict["scaled_values"].keys()), (
        "raw_values and scaled_values must have the same set of address keys"
    )
    # failed_addresses entries are ints matching snapshot.failed_addresses
    assert sorted(enqueue_dict["failed_addresses"]) == sorted(snapshot.failed_addresses), (
        f"failed_addresses mismatch: "
        f"got {sorted(enqueue_dict['failed_addresses'])}, "
        f"expected {sorted(snapshot.failed_addresses)}"
    )

    # Req 7.3: JSON-serialisable — json.dumps must not raise
    try:
        serialized = json.dumps(enqueue_dict)
    except (TypeError, ValueError) as exc:
        raise AssertionError(f"Enqueue payload is not JSON-serialisable: {exc}") from exc

    # Req 7.4: full round-trip preserves all fields
    roundtripped = json.loads(serialized)

    assert roundtripped["slave_id"] == enqueue_dict["slave_id"], (
        f"Round-trip slave_id mismatch: got {roundtripped['slave_id']}, "
        f"expected {enqueue_dict['slave_id']}"
    )
    assert roundtripped["timestamp"] == enqueue_dict["timestamp"], (
        f"Round-trip timestamp mismatch: got {roundtripped['timestamp']!r}, "
        f"expected {enqueue_dict['timestamp']!r}"
    )
    assert roundtripped["raw_values"] == enqueue_dict["raw_values"], (
        "Round-trip raw_values mismatch"
    )
    assert roundtripped["scaled_values"] == enqueue_dict["scaled_values"], (
        "Round-trip scaled_values mismatch"
    )
    assert sorted(roundtripped["failed_addresses"]) == sorted(
        enqueue_dict["failed_addresses"]
    ), "Round-trip failed_addresses mismatch"

    # -----------------------------------------------------------------------
    # Part B: execute() enqueues exactly once (Req 7.1)
    # -----------------------------------------------------------------------
    # Build a use-case with the same read result, but with non-empty raw_values
    # so the persist+enqueue path is taken (not the zero-register skip path).
    mock_gateway = MagicMock()
    mock_gateway.read_snapshot.return_value = read_result

    mock_repo = MagicMock()
    mock_repo.save.return_value = None

    mock_queue = MagicMock()
    mock_queue.enqueue.return_value = None

    mock_mqtt = MagicMock()
    mock_mqtt.publish_controller_snapshot.return_value = True

    settings_obj = _make_settings(register_map)

    use_case = PollControllerUseCase(
        controller_gateway=mock_gateway,
        snapshot_repo=mock_repo,
        reading_queue=mock_queue,
        mqtt_publisher=mock_mqtt,
        settings=settings_obj,
    )

    result = use_case.execute(elevator_id)

    # Req 7.1: enqueue called exactly once
    assert mock_queue.enqueue.call_count == 1, (
        f"queue.enqueue must be called exactly once per successful cycle; "
        f"got {mock_queue.enqueue.call_count} calls"
    )

    # The single argument passed to enqueue must be a dict (JSON-serialisable)
    enqueue_call_args = mock_queue.enqueue.call_args
    assert enqueue_call_args is not None
    enqueued_arg = enqueue_call_args[0][0]  # positional first arg
    assert isinstance(enqueued_arg, dict), (
        f"Argument passed to enqueue must be a dict, got {type(enqueued_arg)}"
    )

    # Req 7.2: the argument contains the required fields
    assert "raw_values" in enqueued_arg
    assert "scaled_values" in enqueued_arg
    assert "slave_id" in enqueued_arg
    assert "timestamp" in enqueued_arg
    assert "failed_addresses" in enqueued_arg

    # Req 7.3: the argument is JSON-serialisable
    try:
        json.dumps(enqueued_arg)
    except (TypeError, ValueError) as exc:
        raise AssertionError(
            f"Argument passed to enqueue is not JSON-serialisable: {exc}"
        ) from exc

    # Req 7.1: execute() is called twice — enqueue still called exactly once per call
    result2 = use_case.execute(elevator_id)
    assert mock_queue.enqueue.call_count == 2, (
        f"After two successful execute() calls, enqueue must have been called exactly 2 "
        f"times total (once per cycle); got {mock_queue.enqueue.call_count}"
    )
    # Both calls used distinct enqueue args (each snapshot has a fresh timestamp)
    first_arg = mock_queue.enqueue.call_args_list[0][0][0]
    second_arg = mock_queue.enqueue.call_args_list[1][0][0]
    assert first_arg["slave_id"] == second_arg["slave_id"] == slave_id


# ---------------------------------------------------------------------------
# Property 13: Controller poll failures are contained
# ---------------------------------------------------------------------------

# Strategies for failure injection

# Gateway-level failures: any exception type that might be raised by a real gateway
_gateway_exception_st = st.one_of(
    st.just(RuntimeError("simulated transport failure")),
    st.just(OSError("simulated OS error")),
    st.just(ConnectionError("simulated connection drop")),
    st.just(TimeoutError("simulated timeout")),
    st.just(ValueError("simulated value error")),
    st.just(Exception("simulated generic exception")),
)

# Repo-level failures
_repo_exception_st = st.one_of(
    st.just(RuntimeError("simulated DB write failure")),
    st.just(OSError("simulated file system error")),
    st.just(Exception("simulated generic persistence error")),
)

# MQTT-level failures
_mqtt_exception_st = st.one_of(
    st.just(RuntimeError("simulated MQTT broker disconnect")),
    st.just(ConnectionError("simulated MQTT connection failure")),
    st.just(TimeoutError("simulated MQTT publish timeout")),
    st.just(Exception("simulated generic MQTT error")),
)

# Queue-level failures
_queue_exception_st = st.one_of(
    st.just(RuntimeError("simulated queue full")),
    st.just(ConnectionError("simulated Redis connection failure")),
    st.just(Exception("simulated generic enqueue error")),
)


def _make_failing_gateway_use_case(
    exc: Exception,
    register_map: list[RegisterEntryConfig],
    elevator_id: str,
) -> PollControllerUseCase:
    """Wire a use case whose gateway raises the supplied exception."""
    mock_gateway = MagicMock()
    mock_gateway.read_snapshot.side_effect = exc

    mock_repo = MagicMock()
    mock_queue = MagicMock()
    mock_mqtt = MagicMock()
    mock_mqtt.publish_controller_snapshot.return_value = True

    return PollControllerUseCase(
        controller_gateway=mock_gateway,
        snapshot_repo=mock_repo,
        reading_queue=mock_queue,
        mqtt_publisher=mock_mqtt,
        settings=_make_settings(register_map),
    )


def _make_downstream_failing_use_case(
    slave_id: int,
    raw_values: dict[int, int],
    register_map: list[RegisterEntryConfig],
    repo_exc: Exception | None = None,
    queue_exc: Exception | None = None,
    mqtt_exc: Exception | None = None,
) -> tuple[PollControllerUseCase, MagicMock, MagicMock, MagicMock]:
    """Wire a use case with a healthy gateway but optionally failing downstream deps."""
    read_result = ControllerReadResult(
        status=ControllerReadStatus.OK,
        slave_id=slave_id,
        raw_values=dict(raw_values),
        failed_addresses=(),
    )

    mock_gateway = MagicMock()
    mock_gateway.read_snapshot.return_value = read_result

    mock_repo = MagicMock()
    if repo_exc is not None:
        mock_repo.save.side_effect = repo_exc

    mock_queue = MagicMock()
    if queue_exc is not None:
        mock_queue.enqueue.side_effect = queue_exc

    mock_mqtt = MagicMock()
    if mqtt_exc is not None:
        mock_mqtt.publish_controller_snapshot.side_effect = mqtt_exc
    else:
        mock_mqtt.publish_controller_snapshot.return_value = True

    use_case = PollControllerUseCase(
        controller_gateway=mock_gateway,
        snapshot_repo=mock_repo,
        reading_queue=mock_queue,
        mqtt_publisher=mock_mqtt,
        settings=_make_settings(register_map),
    )
    return use_case, mock_repo, mock_queue, mock_mqtt


# Feature: modbus-controller-telemetry, Property 13: Controller poll failures are contained
@given(
    exc=_gateway_exception_st,
    elevator_id=_elevator_id_st,
    register_map=_register_map_st,
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_gateway_exception_is_contained_and_does_not_propagate(
    exc: Exception,
    elevator_id: str,
    register_map: list[RegisterEntryConfig],
) -> None:
    """Any exception raised by the controller gateway is caught within the controller
    poll path and never propagates as an unhandled exception to the caller.

    The existing field-sensor poll cycle (modelled here as code running after
    ``execute()``) must be able to complete its steps without interruption.

    Checks:
    - execute() does not raise when the gateway raises any exception (Req 6.5)
    - execute() returns a PollControllerResult (not None) (Req 6.4)
    - The returned result indicates failure (Req 6.4)
    - Code following execute() in the same call stack is reachable (Req 6.5)

    Validates: Requirements 6.4, 6.5
    """
    use_case = _make_failing_gateway_use_case(exc, register_map, elevator_id)

    # Sentinel to confirm that code following execute() is reachable (R6.5).
    sensor_cycle_completed = False

    # execute() must never propagate the gateway exception.
    try:
        result = use_case.execute(elevator_id)
    except Exception as propagated:
        raise AssertionError(
            f"execute() must not propagate controller-gateway exceptions to the caller, "
            f"but raised {type(propagated).__name__}: {propagated}"
        ) from propagated

    # Simulated field-sensor cycle — must be reachable regardless of controller failure.
    sensor_cycle_completed = True

    # R6.4: result is always returned, never None.
    assert result is not None, "execute() must return a PollControllerResult, got None"

    # R6.4: gateway failure causes a non-success result.
    assert not result.success, (
        f"execute() should report failure when the gateway raises, got success=True"
    )

    # R6.5: code after execute() ran (field-sensor cycle was not blocked).
    assert sensor_cycle_completed, (
        "Code following execute() must be reachable; the controller failure "
        "must be fully contained within the controller poll path."
    )


# Feature: modbus-controller-telemetry, Property 13: Controller poll failures are contained
@given(
    slave_id=_slave_id_st,
    raw_values=_nonempty_raw_values_st,
    register_map=_register_map_st,
    mqtt_exc=_mqtt_exception_st,
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_mqtt_failure_is_contained_and_cycle_continues(
    slave_id: int,
    raw_values: dict[int, int],
    register_map: list[RegisterEntryConfig],
    mqtt_exc: Exception,
) -> None:
    """An MQTT publish failure is caught within the controller poll path.

    The use case must return a success result (snapshot was persisted) and the
    exception must not propagate, so the field-sensor cycle remains unaffected.

    Checks:
    - execute() does not raise when MQTT raises any exception (Req 6.5, R5.6)
    - execute() returns success=True because persist succeeded (Req 6.4)
    - The snapshot is still returned in the result (Req 5.6)
    - Code following execute() is reachable (Req 6.5)

    Validates: Requirements 6.4, 6.5
    """
    use_case, mock_repo, mock_queue, mock_mqtt = _make_downstream_failing_use_case(
        slave_id=slave_id,
        raw_values=raw_values,
        register_map=register_map,
        mqtt_exc=mqtt_exc,
    )

    sensor_cycle_completed = False

    try:
        result = use_case.execute("elev-test")
    except Exception as propagated:
        raise AssertionError(
            f"execute() must not propagate MQTT exceptions, "
            f"but raised {type(propagated).__name__}: {propagated}"
        ) from propagated

    sensor_cycle_completed = True

    # R6.4: result is returned.
    assert result is not None

    # MQTT failure is non-fatal: persist succeeded so overall cycle is a success.
    assert result.success, (
        "execute() must report success when only MQTT publish fails "
        "(snapshot was already persisted)"
    )

    # Snapshot is retained and returned (R5.6).
    assert result.snapshot is not None, "Snapshot must be retained when MQTT publish fails"

    # Persist was still called (the MQTT failure did not short-circuit it).
    mock_repo.save.assert_called_once()

    # R6.5: field-sensor cycle was not blocked.
    assert sensor_cycle_completed


# Feature: modbus-controller-telemetry, Property 13: Controller poll failures are contained
@given(
    slave_id=_slave_id_st,
    raw_values=_nonempty_raw_values_st,
    register_map=_register_map_st,
    queue_exc=_queue_exception_st,
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_enqueue_failure_is_contained_and_cycle_continues(
    slave_id: int,
    raw_values: dict[int, int],
    register_map: list[RegisterEntryConfig],
    queue_exc: Exception,
) -> None:
    """An enqueue failure is caught within the controller poll path.

    Persist has already succeeded at the point of enqueue failure, so the cycle
    must still report success and the snapshot must be retained.

    Checks:
    - execute() does not raise when enqueue raises any exception (Req 6.5, R7.5)
    - execute() returns success=True because persist succeeded (Req 6.4)
    - Snapshot is retained (Req 7.5)
    - Code following execute() is reachable (Req 6.5)

    Validates: Requirements 6.4, 6.5
    """
    use_case, mock_repo, mock_queue, mock_mqtt = _make_downstream_failing_use_case(
        slave_id=slave_id,
        raw_values=raw_values,
        register_map=register_map,
        queue_exc=queue_exc,
    )

    sensor_cycle_completed = False

    try:
        result = use_case.execute("elev-test")
    except Exception as propagated:
        raise AssertionError(
            f"execute() must not propagate enqueue exceptions, "
            f"but raised {type(propagated).__name__}: {propagated}"
        ) from propagated

    sensor_cycle_completed = True

    assert result is not None

    # Enqueue failure is non-fatal: persist succeeded.
    assert result.success, (
        "execute() must report success when only enqueue fails "
        "(snapshot was already persisted)"
    )

    # Snapshot is retained (Req 7.5).
    assert result.snapshot is not None, "Snapshot must be retained when enqueue fails"

    # Persist was still called and succeeded.
    mock_repo.save.assert_called_once()

    # MQTT was still attempted after the enqueue failure (independent paths).
    mock_mqtt.publish_controller_snapshot.assert_called_once()

    # R6.5: field-sensor cycle was not blocked.
    assert sensor_cycle_completed


# Feature: modbus-controller-telemetry, Property 13: Controller poll failures are contained
@given(
    slave_id=_slave_id_st,
    raw_values=_nonempty_raw_values_st,
    register_map=_register_map_st,
    queue_exc=_queue_exception_st,
    mqtt_exc=_mqtt_exception_st,
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_combined_enqueue_and_mqtt_failure_is_contained(
    slave_id: int,
    raw_values: dict[int, int],
    register_map: list[RegisterEntryConfig],
    queue_exc: Exception,
    mqtt_exc: Exception,
) -> None:
    """Both enqueue and MQTT failures occurring together are fully contained.

    When both downstream paths raise, persist has already succeeded, so the
    cycle must still return success and the snapshot must be retained.

    Checks:
    - execute() does not raise when both enqueue and MQTT raise (Req 6.5)
    - execute() returns success=True because persist succeeded (Req 6.4)
    - Snapshot is retained unchanged (Req 5.6, 7.5)
    - Code following execute() is reachable (Req 6.5)

    Validates: Requirements 6.4, 6.5
    """
    use_case, mock_repo, mock_queue, mock_mqtt = _make_downstream_failing_use_case(
        slave_id=slave_id,
        raw_values=raw_values,
        register_map=register_map,
        queue_exc=queue_exc,
        mqtt_exc=mqtt_exc,
    )

    sensor_cycle_completed = False

    try:
        result = use_case.execute("elev-test")
    except Exception as propagated:
        raise AssertionError(
            f"execute() must not propagate downstream exceptions when both enqueue "
            f"and MQTT fail, but raised {type(propagated).__name__}: {propagated}"
        ) from propagated

    sensor_cycle_completed = True

    assert result is not None

    # Persist succeeded → overall cycle is still a success.
    assert result.success, (
        "execute() must report success when only downstream (enqueue + MQTT) paths fail"
    )

    # Snapshot is retained.
    assert result.snapshot is not None

    # Persist was called once; enqueue and MQTT were both attempted.
    mock_repo.save.assert_called_once()
    mock_queue.enqueue.assert_called_once()
    mock_mqtt.publish_controller_snapshot.assert_called_once()

    # R6.5: field-sensor cycle was not blocked.
    assert sensor_cycle_completed


# Feature: modbus-controller-telemetry, Property 13: Controller poll failures are contained
@given(
    status=st.sampled_from([
        ControllerReadStatus.INVALID_SLAVE_ID,
        ControllerReadStatus.CONNECTION_UNAVAILABLE,
    ]),
    slave_id=_slave_id_st,
    elevator_id=_elevator_id_st,
    register_map=_register_map_st,
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_non_ok_gateway_status_is_contained_and_does_not_propagate(
    status: ControllerReadStatus,
    slave_id: int,
    elevator_id: str,
    register_map: list[RegisterEntryConfig],
) -> None:
    """A non-OK gateway status result (INVALID_SLAVE_ID, CONNECTION_UNAVAILABLE)
    is contained within the controller poll path and never propagates as an exception.

    The field-sensor cycle must still be able to run after a hard-fail gateway status.

    Checks:
    - execute() does not raise for any non-OK gateway status (Req 6.5)
    - execute() returns success=False (Req 6.4)
    - Code following execute() is reachable (Req 6.5)

    Validates: Requirements 6.4, 6.5
    """
    read_result = ControllerReadResult(
        status=status,
        slave_id=slave_id,
        raw_values={},
        failed_addresses=(),
    )

    mock_gateway = MagicMock()
    mock_gateway.read_snapshot.return_value = read_result

    mock_repo = MagicMock()
    mock_queue = MagicMock()
    mock_mqtt = MagicMock()

    use_case = PollControllerUseCase(
        controller_gateway=mock_gateway,
        snapshot_repo=mock_repo,
        reading_queue=mock_queue,
        mqtt_publisher=mock_mqtt,
        settings=_make_settings(register_map),
    )

    sensor_cycle_completed = False

    try:
        result = use_case.execute(elevator_id)
    except Exception as propagated:
        raise AssertionError(
            f"execute() must not propagate for non-OK status {status.value}, "
            f"but raised {type(propagated).__name__}: {propagated}"
        ) from propagated

    sensor_cycle_completed = True

    assert result is not None

    # R6.4: hard-fail statuses produce a failure result.
    assert not result.success, (
        f"execute() must report failure for gateway status {status.value}, got success=True"
    )

    # No I/O side-effects should have been attempted (persist/enqueue/mqtt).
    mock_repo.save.assert_not_called()
    mock_queue.enqueue.assert_not_called()
    mock_mqtt.publish_controller_snapshot.assert_not_called()

    # R6.5: field-sensor cycle was not blocked.
    assert sensor_cycle_completed


# Feature: modbus-controller-telemetry, Property 13: Controller poll failures are contained
@given(
    exc=_gateway_exception_st,
    elevator_id=_elevator_id_st,
    register_map=_register_map_st,
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_run_forever_gateway_exception_does_not_terminate_loop(
    exc: Exception,
    elevator_id: str,
    register_map: list[RegisterEntryConfig],
) -> None:
    """run_forever() contains per-cycle controller failures so the loop continues.

    Even if execute() itself were to escape a cycle (belt-and-suspenders path
    in run_forever), the loop must catch it and proceed to the next cycle.

    Checks:
    - run_forever() with max_cycles=2 does not raise when execute() raises (Req 6.5)
    - All cycles are attempted despite failures (Req 6.4)

    Validates: Requirements 6.4, 6.5
    """
    # Make the gateway raise on every call.
    mock_gateway = MagicMock()
    mock_gateway.read_snapshot.side_effect = exc

    mock_repo = MagicMock()
    mock_queue = MagicMock()
    mock_mqtt = MagicMock()

    use_case = PollControllerUseCase(
        controller_gateway=mock_gateway,
        snapshot_repo=mock_repo,
        reading_queue=mock_queue,
        mqtt_publisher=mock_mqtt,
        settings=_make_settings(register_map),
    )

    # run_forever() must not raise; use max_cycles=2 and no-op sleep to keep it fast.
    try:
        use_case.run_forever(
            elevator_id,
            max_cycles=2,
            sleep_fn=lambda _: None,
        )
    except Exception as propagated:
        raise AssertionError(
            f"run_forever() must not propagate controller-cycle exceptions, "
            f"but raised {type(propagated).__name__}: {propagated}"
        ) from propagated

    # Gateway was called for both cycles (failures did not abort the loop).
    assert mock_gateway.read_snapshot.call_count == 2, (
        f"Gateway should have been called 2 times (once per cycle), "
        f"got {mock_gateway.read_snapshot.call_count}"
    )


# ---------------------------------------------------------------------------
# Property 14: Poll interval defaults when unconfigured
# ---------------------------------------------------------------------------

# Strategy: draw poll_interval_s values covering:
#   - the default (5)
#   - zero / falsy (0) — "unconfigured" branch that must also yield 5 s
#   - arbitrary positive integers that should be used as-is
_poll_interval_st = st.one_of(
    st.just(0),       # falsy → default 5 s (R9.2)
    st.just(5),       # the default value itself
    st.integers(min_value=1, max_value=3600),  # any configured positive value
)


def _make_use_case_with_interval(
    poll_interval_s: int,
    register_map: list[RegisterEntryConfig],
) -> tuple[PollControllerUseCase, MagicMock]:
    """Wire a use case with the given poll interval; gateway always succeeds with one register."""
    read_result = ControllerReadResult(
        status=ControllerReadStatus.OK,
        slave_id=1,
        raw_values={100: 42},
        failed_addresses=(),
    )
    mock_gateway = MagicMock()
    mock_gateway.read_snapshot.return_value = read_result

    mock_repo = MagicMock()
    mock_queue = MagicMock()
    mock_mqtt = MagicMock()
    mock_mqtt.publish_controller_snapshot.return_value = True

    telemetry_cfg = ControllerTelemetryConfig(
        poll_interval_s=poll_interval_s,
        register_map=register_map,
    )
    settings_obj = Settings(controller_telemetry=telemetry_cfg)

    use_case = PollControllerUseCase(
        controller_gateway=mock_gateway,
        snapshot_repo=mock_repo,
        reading_queue=mock_queue,
        mqtt_publisher=mock_mqtt,
        settings=settings_obj,
    )
    mock_sleep = MagicMock()
    return use_case, mock_sleep


# Feature: modbus-controller-telemetry, Property 14: Poll interval defaults when unconfigured
@given(
    poll_interval_s=_poll_interval_st,
    register_map=_register_map_st,
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_poll_interval_defaults_when_unconfigured(
    poll_interval_s: int,
    register_map: list[RegisterEntryConfig],
) -> None:
    """run_forever() uses the configured poll interval, defaulting to 5 seconds when
    the configured value is falsy (zero / not set).

    For any Settings configuration the effective poll interval must be:
    - 5.0 seconds when poll_interval_s is 0 (falsy / "unconfigured") — R9.2
    - float(poll_interval_s) when poll_interval_s is a positive integer — R9.1, R9.3

    The test runs exactly 2 cycles with a mock sleep function and verifies that
    sleep is called exactly once (between cycles) with the correct interval.

    Validates: Requirements 9.2
    """
    use_case, mock_sleep = _make_use_case_with_interval(poll_interval_s, register_map)

    # R9.2: the expected effective interval
    expected_interval: float = float(poll_interval_s) if poll_interval_s else 5.0

    # Run exactly 2 cycles; sleep is called once between them.
    use_case.run_forever(
        "elev-p14",
        max_cycles=2,
        sleep_fn=mock_sleep,
    )

    # sleep must be called exactly once (between cycle 1 and cycle 2).
    assert mock_sleep.call_count == 1, (
        f"sleep must be called exactly once for 2 cycles "
        f"(poll_interval_s={poll_interval_s}), got {mock_sleep.call_count} calls"
    )

    # The single sleep call must use the correct effective interval.
    actual_interval = mock_sleep.call_args[0][0]
    assert actual_interval == expected_interval, (
        f"sleep was called with interval={actual_interval!r} but expected "
        f"{expected_interval!r} (poll_interval_s={poll_interval_s})"
    )

    # R9.2: when unconfigured (0), the default MUST be exactly 5 seconds.
    if poll_interval_s == 0:
        assert actual_interval == 5.0, (
            f"Default poll interval must be 5 s when poll_interval_s=0; "
            f"got {actual_interval!r}"
        )

    # R9.1 / R9.3: when configured, the interval matches the setting exactly.
    if poll_interval_s > 0:
        assert actual_interval == float(poll_interval_s), (
            f"Effective interval {actual_interval!r} does not match "
            f"configured poll_interval_s={poll_interval_s}"
        )


# ===========================================================================
# Task 5.9 — Example tests for use-case branches
# ===========================================================================
# These are concrete, deterministic unit tests (no Hypothesis) that target
# specific branches in PollControllerUseCase.execute() and run_forever().
# Requirements covered: 4.2, 5.4, 5.6, 5.7, 7.5, 9.1, 9.3, 10.4
# ===========================================================================

import time as _time_module  # used only for a real-time guard in the persist-within-2s test


# ---------------------------------------------------------------------------
# Helpers shared across example tests
# ---------------------------------------------------------------------------

_SAMPLE_REGISTER_MAP: list[RegisterEntryConfig] = [
    RegisterEntryConfig(address=100, key="reg_100", meaning="Speed", scale="/10", unit="rpm"),
    RegisterEntryConfig(address=101, key="reg_101", meaning="Voltage", scale="/100", unit="V"),
    RegisterEntryConfig(address=102, key="reg_102", meaning="Status", scale="", unit=""),
]


def _ok_read_result(
    slave_id: int = 1,
    raw_values: dict[int, int] | None = None,
    failed_addresses: tuple[int, ...] = (),
) -> ControllerReadResult:
    if raw_values is None:
        raw_values = {100: 1500, 101: 22000, 102: 1}
    return ControllerReadResult(
        status=ControllerReadStatus.OK,
        slave_id=slave_id,
        raw_values=raw_values,
        failed_addresses=failed_addresses,
    )


def _build_use_case(
    read_result: ControllerReadResult,
    register_map: list[RegisterEntryConfig] | None = None,
    repo_exc: Exception | None = None,
    queue_exc: Exception | None = None,
    mqtt_return: bool = True,
    mqtt_exc: Exception | None = None,
) -> tuple[PollControllerUseCase, MagicMock, MagicMock, MagicMock]:
    if register_map is None:
        register_map = _SAMPLE_REGISTER_MAP

    mock_gateway = MagicMock()
    mock_gateway.read_snapshot.return_value = read_result

    mock_repo = MagicMock()
    if repo_exc is not None:
        mock_repo.save.side_effect = repo_exc

    mock_queue = MagicMock()
    if queue_exc is not None:
        mock_queue.enqueue.side_effect = queue_exc

    mock_mqtt = MagicMock()
    if mqtt_exc is not None:
        mock_mqtt.publish_controller_snapshot.side_effect = mqtt_exc
    else:
        mock_mqtt.publish_controller_snapshot.return_value = mqtt_return

    uc = PollControllerUseCase(
        controller_gateway=mock_gateway,
        snapshot_repo=mock_repo,
        reading_queue=mock_queue,
        mqtt_publisher=mock_mqtt,
        settings=_make_settings(register_map),
    )
    return uc, mock_repo, mock_queue, mock_mqtt


# ---------------------------------------------------------------------------
# Req 4.2 — persist-within-2 s
# ---------------------------------------------------------------------------

def test_persist_is_called_within_two_seconds() -> None:
    """repo.save() completes within 2 seconds of snapshot production (Req 4.2).

    Measures wall-clock time to confirm the persist call completes well within
    the 2-second SLA.  With a synchronous mock save() there should be no delay.
    """
    read_result = _ok_read_result()
    uc, mock_repo, _, _ = _build_use_case(read_result)

    start = _time_module.monotonic()
    result = uc.execute("elev-persist-test")
    elapsed = _time_module.monotonic() - start

    mock_repo.save.assert_called_once()
    # Allow 1 s as a conservative ceiling for slow CI environments.
    assert elapsed < 1.0, (
        f"execute() took {elapsed:.3f}s which approaches the 2-second persist SLA (Req 4.2)"
    )
    assert result.success
    assert result.snapshot is not None


def test_persist_receives_the_snapshot_built_in_the_same_cycle() -> None:
    """The object passed to repo.save() is the snapshot returned in the result (Req 4.2)."""
    read_result = _ok_read_result(slave_id=7, raw_values={100: 42})
    uc, mock_repo, _, _ = _build_use_case(read_result)

    result = uc.execute("elev-persist-check")

    assert result.snapshot is not None
    saved_snapshot = mock_repo.save.call_args[0][0]
    assert saved_snapshot is result.snapshot
    assert saved_snapshot.slave_id == 7
    assert saved_snapshot.raw_values.get(100) == 42


# ---------------------------------------------------------------------------
# Req 5.7 / Req 10.4 — zero-register cycle
# ---------------------------------------------------------------------------

def test_zero_register_cycle_skips_persist_and_enqueue() -> None:
    """When zero registers are read successfully, persist and enqueue are skipped (Req 10.4).

    A slave_id-only payload must still be published to MQTT (Req 5.7) and
    the cycle must report success=True.
    """
    read_result = _ok_read_result(slave_id=3, raw_values={}, failed_addresses=(100, 101, 102))
    uc, mock_repo, mock_queue, mock_mqtt = _build_use_case(read_result)

    result = uc.execute("elev-zero")

    mock_repo.save.assert_not_called()
    mock_queue.enqueue.assert_not_called()

    # MQTT must receive a slave_id-only payload (Req 5.7).
    mock_mqtt.publish_controller_snapshot.assert_called_once()
    published_payload = mock_mqtt.publish_controller_snapshot.call_args[0][0]
    assert set(published_payload.keys()) == {"slave_id"}, (
        f"Zero-register cycle must publish only slave_id, got keys: "
        f"{set(published_payload.keys())}"
    )
    assert published_payload["slave_id"] == 3

    assert result.success
    assert result.snapshot is not None
    assert not result.snapshot.raw_values


def test_zero_register_cycle_uses_publish_controller_snapshot_not_publish_reading() -> None:
    """The zero-register publish path calls publish_controller_snapshot, not publish_reading."""
    read_result = _ok_read_result(raw_values={})
    uc, _, _, mock_mqtt = _build_use_case(read_result)

    uc.execute("elev-zero-method")

    assert mock_mqtt.publish_controller_snapshot.call_count == 1
    mock_mqtt.publish_reading.assert_not_called()


def test_zero_register_cycle_publish_failure_is_tolerated() -> None:
    """A publish failure during the zero-register path is tolerated (Req 5.6)."""
    read_result = _ok_read_result(raw_values={})
    uc, mock_repo, mock_queue, _ = _build_use_case(
        read_result, mqtt_exc=RuntimeError("broker unavailable")
    )

    result = uc.execute("elev-zero-publish-fail")

    assert result is not None
    assert result.success
    mock_repo.save.assert_not_called()
    mock_queue.enqueue.assert_not_called()


# ---------------------------------------------------------------------------
# Req 5.4 — QoS 1 for controller snapshot publish
# ---------------------------------------------------------------------------

def test_publish_controller_snapshot_is_called_not_publish_reading() -> None:
    """publish_controller_snapshot() is the only MQTT method called (Req 5.4).

    The use case must NOT call publish_reading() or publish_status() —
    those belong to the field-sensor path.  The controller telemetry adapter
    uses publish_controller_snapshot(), which internally applies QoS=1.
    """
    read_result = _ok_read_result(raw_values={100: 9999})
    uc, _, _, mock_mqtt = _build_use_case(read_result)

    uc.execute("elev-qos-check")

    assert mock_mqtt.publish_controller_snapshot.call_count == 1
    mock_mqtt.publish_reading.assert_not_called()
    mock_mqtt.publish_status.assert_not_called()


def test_publish_controller_snapshot_receives_full_flat_payload() -> None:
    """Payload passed to publish_controller_snapshot contains all registers + slave_id (Req 5.2, 5.3)."""
    raw = {100: 1500, 101: 22000, 102: 1}
    read_result = _ok_read_result(slave_id=5, raw_values=raw)
    uc, _, _, mock_mqtt = _build_use_case(read_result)

    uc.execute("elev-full-payload")

    payload = mock_mqtt.publish_controller_snapshot.call_args[0][0]
    assert payload["slave_id"] == 5
    assert isinstance(payload["slave_id"], int)
    for addr, expected_raw in raw.items():
        assert str(addr) in payload, f"Missing key '{addr}' in flat payload"
        assert payload[str(addr)] == expected_raw


# ---------------------------------------------------------------------------
# Req 5.6 — tolerated publish failure (non-zero-register path)
# ---------------------------------------------------------------------------

def test_tolerated_publish_failure_returns_false() -> None:
    """publish_controller_snapshot() returning False is treated as non-fatal (Req 5.6)."""
    read_result = _ok_read_result(raw_values={100: 42})
    uc, mock_repo, mock_queue, _ = _build_use_case(read_result, mqtt_return=False)

    result = uc.execute("elev-publish-false")

    mock_repo.save.assert_called_once()
    mock_queue.enqueue.assert_called_once()
    assert result.success
    assert result.snapshot is not None


def test_tolerated_publish_exception_does_not_abort_cycle() -> None:
    """An exception from publish_controller_snapshot is caught; cycle reports success (Req 5.6)."""
    read_result = _ok_read_result(raw_values={100: 42})
    uc, mock_repo, mock_queue, _ = _build_use_case(
        read_result, mqtt_exc=ConnectionError("broker went away")
    )

    result = uc.execute("elev-publish-exc")

    assert result is not None
    mock_repo.save.assert_called_once()
    mock_queue.enqueue.assert_called_once()
    assert result.success
    assert result.snapshot is not None


def test_publish_failure_does_not_prevent_enqueue() -> None:
    """Enqueue runs before publish; a publish exception cannot retroactively skip enqueue.

    This verifies the independent try/except ordering: persist -> enqueue -> publish.
    """
    read_result = _ok_read_result(raw_values={100: 42})
    uc, mock_repo, mock_queue, mock_mqtt = _build_use_case(
        read_result, mqtt_exc=TimeoutError("publish timed out")
    )

    uc.execute("elev-order-check")

    mock_repo.save.assert_called_once()
    mock_queue.enqueue.assert_called_once()
    mock_mqtt.publish_controller_snapshot.assert_called_once()


# ---------------------------------------------------------------------------
# Req 7.5 — tolerated enqueue failure
# ---------------------------------------------------------------------------

def test_tolerated_enqueue_failure_still_reports_success() -> None:
    """An enqueue failure is caught; cycle reports success because persist already succeeded (Req 7.5)."""
    read_result = _ok_read_result(raw_values={100: 42})
    uc, mock_repo, mock_queue, mock_mqtt = _build_use_case(
        read_result, queue_exc=RuntimeError("Redis connection lost")
    )

    result = uc.execute("elev-enqueue-fail")

    mock_repo.save.assert_called_once()
    mock_queue.enqueue.assert_called_once()
    # MQTT publish is still attempted after the enqueue failure.
    mock_mqtt.publish_controller_snapshot.assert_called_once()
    assert result.success
    assert result.snapshot is not None


def test_tolerated_enqueue_failure_does_not_suppress_mqtt() -> None:
    """MQTT publish is attempted even when enqueue raises (Req 7.5 independent paths)."""
    read_result = _ok_read_result(raw_values={101: 5000})
    uc, _, mock_queue, mock_mqtt = _build_use_case(
        read_result, queue_exc=ConnectionError("queue unavailable")
    )

    uc.execute("elev-enqueue-mqtt-order")

    mock_queue.enqueue.assert_called_once()
    mock_mqtt.publish_controller_snapshot.assert_called_once()


# ---------------------------------------------------------------------------
# Req 9.1 / 9.3 — repeated cycles honoring the poll interval
# ---------------------------------------------------------------------------

def test_run_forever_calls_sleep_between_cycles_with_correct_interval() -> None:
    """run_forever() calls sleep exactly N-1 times for N cycles, with the configured interval (Req 9.1, 9.3)."""
    read_result = _ok_read_result(raw_values={100: 1})
    uc, _, _, _ = _build_use_case(read_result)

    uc._settings.controller_telemetry.poll_interval_s = 10

    mock_sleep = MagicMock()
    uc.run_forever("elev-interval", max_cycles=3, sleep_fn=mock_sleep)

    # 3 cycles -> 2 sleeps.
    assert mock_sleep.call_count == 2, (
        f"Expected 2 sleep calls for 3 cycles, got {mock_sleep.call_count}"
    )
    for idx, call_args in enumerate(mock_sleep.call_args_list):
        interval = call_args[0][0]
        assert interval == 10.0, (
            f"Sleep call {idx} used interval {interval!r}, expected 10.0"
        )


def test_run_forever_executes_all_requested_cycles() -> None:
    """run_forever() with max_cycles=N calls execute() exactly N times (Req 9.1)."""
    read_result = _ok_read_result(raw_values={100: 1})
    uc, _, mock_queue, _ = _build_use_case(read_result)

    uc.run_forever("elev-cycle-count", max_cycles=5, sleep_fn=lambda _: None)

    assert uc._gateway.read_snapshot.call_count == 5
    assert mock_queue.enqueue.call_count == 5


def test_run_forever_defaults_to_five_second_interval_when_zero() -> None:
    """When poll_interval_s is 0 (falsy), run_forever() uses 5 s (Req 9.2)."""
    read_result = _ok_read_result(raw_values={100: 1})
    uc, _, _, _ = _build_use_case(read_result)

    uc._settings.controller_telemetry.poll_interval_s = 0

    mock_sleep = MagicMock()
    uc.run_forever("elev-default-interval", max_cycles=2, sleep_fn=mock_sleep)

    assert mock_sleep.call_count == 1
    actual_interval = mock_sleep.call_args[0][0]
    assert actual_interval == 5.0, (
        f"Default poll interval must be 5.0 when poll_interval_s=0, got {actual_interval}"
    )


def test_run_forever_continues_after_per_cycle_failure() -> None:
    """run_forever() continues to the next cycle even when a cycle returns failure (Req 9.1)."""
    fail_result = ControllerReadResult(
        status=ControllerReadStatus.INVALID_SLAVE_ID,
        slave_id=0,
        raw_values={},
        failed_addresses=(),
    )
    success_result = _ok_read_result(raw_values={100: 1})

    mock_gateway = MagicMock()
    mock_gateway.read_snapshot.side_effect = [fail_result, success_result]

    mock_repo = MagicMock()
    mock_queue = MagicMock()
    mock_mqtt = MagicMock()
    mock_mqtt.publish_controller_snapshot.return_value = True

    uc = PollControllerUseCase(
        controller_gateway=mock_gateway,
        snapshot_repo=mock_repo,
        reading_queue=mock_queue,
        mqtt_publisher=mock_mqtt,
        settings=_make_settings(_SAMPLE_REGISTER_MAP),
    )

    uc.run_forever("elev-fail-then-ok", max_cycles=2, sleep_fn=lambda _: None)

    assert mock_gateway.read_snapshot.call_count == 2
    # Only the second (successful) cycle persisted.
    mock_repo.save.assert_called_once()


def test_run_forever_sleep_uses_float_interval() -> None:
    """The argument passed to sleep_fn is a float (Req 9.3)."""
    read_result = _ok_read_result(raw_values={100: 1})
    uc, _, _, _ = _build_use_case(read_result)

    uc._settings.controller_telemetry.poll_interval_s = 7

    mock_sleep = MagicMock()
    uc.run_forever("elev-float-sleep", max_cycles=2, sleep_fn=mock_sleep)

    actual_interval = mock_sleep.call_args[0][0]
    assert isinstance(actual_interval, float), (
        f"sleep_fn must be called with a float, got {type(actual_interval).__name__}"
    )
    assert actual_interval == 7.0
