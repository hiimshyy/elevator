"""Tests for the pymodbus controller gateway adapter.

Includes property-based tests for slave-id validation and timeout clamping, plus
example/branch tests covering the connection-unavailable path, per-block error
and exception recording, and the inter-block sleep cadence.
"""

import time
from unittest.mock import MagicMock

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pymodbus.exceptions import ModbusException

from elevator_pdm.domain.interfaces.controller_gateway import ControllerReadStatus
from elevator_pdm.infrastructure.config.settings import (
    ControllerTelemetryConfig,
    RegisterEntryConfig,
    Settings,
)
from elevator_pdm.infrastructure.sensors.pymodbus_controller_gateway import (
    DEFAULT_TIMEOUT_MS,
    INTER_BLOCK_DELAY_S,
    MAX_SLAVE_ID,
    MAX_TIMEOUT_MS,
    MIN_SLAVE_ID,
    MIN_TIMEOUT_MS,
    PymodbusControllerGateway,
    clamp_timeout_ms,
)


def _make_mock_client() -> MagicMock:
    """Build a mocked ModbusSerialClient with a successful FC03 response.

    ``connect`` succeeds, ``read_holding_registers`` returns a non-error
    response with ample register data, and ``close`` is a no-op. The mock
    records call counts so the test can assert how many FC03 reads were issued.
    """
    response = MagicMock()
    response.isError.return_value = False
    response.registers = [0] * 125  # max Modbus FC03 register span
    client = MagicMock()
    client.connect.return_value = True
    client.read_holding_registers.return_value = response
    client.close.return_value = None
    return client


def _settings_with_slave_id(slave_id: int) -> Settings:
    """Build Settings whose controller telemetry uses a tiny contiguous map.

    A two-register contiguous map yields a single read block, so the poll path
    issues exactly one FC03 request with no inter-block sleeps, keeping the
    property test fast while still exercising the slave-id gate.
    """
    return Settings(
        controller_telemetry=ControllerTelemetryConfig(
            slave_id=slave_id,
            register_map=[
                RegisterEntryConfig(address=0, key="a"),
                RegisterEntryConfig(address=1, key="b"),
            ],
        )
    )


# Slave ids spanning the valid range, both boundaries, and out-of-range values
# on either side (including zero and negatives).
_slave_ids = st.one_of(
    st.integers(min_value=MIN_SLAVE_ID, max_value=MAX_SLAVE_ID),
    st.integers(min_value=-1000, max_value=1000),
    st.sampled_from([-1, 0, 1, 2, 246, 247, 248, 300]),
)


# Feature: modbus-controller-telemetry, Property 4: Slave id validation gates the poll cycle
@given(slave_id=_slave_ids)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_slave_id_validation_gates_poll_cycle(slave_id: int) -> None:
    """In-range slave ids proceed with FC03 reads; out-of-range ids issue none.

    For any integer slave id in [1, 247] the gateway proceeds with FC03 reads
    and does not return INVALID_SLAVE_ID (Requirement 1.4). For any slave id
    outside that range the gateway returns INVALID_SLAVE_ID and issues zero FC03
    (read_holding_registers) requests (Requirement 1.5).

    Validates: Requirements 1.4, 1.5
    """
    client = _make_mock_client()
    gateway = PymodbusControllerGateway(
        settings=_settings_with_slave_id(slave_id),
        client_factory=lambda: client,
    )

    result = gateway.read_snapshot()

    assert result.slave_id == slave_id

    if MIN_SLAVE_ID <= slave_id <= MAX_SLAVE_ID:
        # Req 1.4: in-range id proceeds with FC03 reads; gate does not trip.
        assert result.status is not ControllerReadStatus.INVALID_SLAVE_ID
        assert client.read_holding_registers.call_count >= 1
    else:
        # Req 1.5: out-of-range id is rejected with zero FC03 requests issued.
        assert result.status is ControllerReadStatus.INVALID_SLAVE_ID
        assert client.read_holding_registers.call_count == 0
        assert client.connect.call_count == 0


# Timeout values spanning below the floor, both boundaries, mid-range, and
# above the ceiling, plus None and negatives as edge cases.
_timeout_values = st.one_of(
    st.none(),
    st.integers(min_value=-1000, max_value=20000),
    st.sampled_from([None, -500, -1, 0, 99, 100, 101, 5000, 9999, 10000, 10001, 50000]),
)


# Feature: modbus-controller-telemetry, Property 5: Per-request timeout is clamped with default
@given(value_ms=_timeout_values)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_timeout_is_clamped_with_default(value_ms: int | None) -> None:
    """Unset timeouts default to 1000 ms; others clamp into [100, 10000].

    When ``value_ms`` is ``None`` the effective per-request timeout SHALL be
    ``DEFAULT_TIMEOUT_MS`` (1000 ms). Otherwise it SHALL equal the value clamped
    into the inclusive range ``[MIN_TIMEOUT_MS, MAX_TIMEOUT_MS]`` and always fall
    within that range (Requirement 1.6).

    Validates: Requirements 1.6
    """
    result = clamp_timeout_ms(value_ms)

    if value_ms is None:
        assert result == DEFAULT_TIMEOUT_MS
    else:
        assert result == max(MIN_TIMEOUT_MS, min(MAX_TIMEOUT_MS, value_ms))

    assert MIN_TIMEOUT_MS <= result <= MAX_TIMEOUT_MS


# --------------------------------------------------------------------------- #
# Example / branch tests
# --------------------------------------------------------------------------- #


def _settings_with_addresses(addresses: list[int], slave_id: int = 1) -> Settings:
    """Build Settings whose register map contains exactly the given addresses.

    The block planner groups strictly contiguous addresses into one block and
    starts a new block on each gap, so the address layout chosen by a test
    directly controls how many FC03 read blocks the poll cycle issues.
    """
    return Settings(
        controller_telemetry=ControllerTelemetryConfig(
            slave_id=slave_id,
            register_map=[
                RegisterEntryConfig(address=address, key=f"r{address}") for address in addresses
            ],
        )
    )


def _ok_response(registers: list[int]) -> MagicMock:
    """Build a non-error FC03 response carrying the given register values."""
    response = MagicMock()
    response.isError.return_value = False
    response.registers = registers
    return response


def _error_response() -> MagicMock:
    """Build an FC03 response that reports a Modbus error via ``isError``."""
    response = MagicMock()
    response.isError.return_value = True
    response.registers = []
    return response


def test_connection_unavailable_returns_status_and_issues_no_reads() -> None:
    """A failed connect yields CONNECTION_UNAVAILABLE with zero FC03 reads.

    When ``client.connect()`` returns False the gateway SHALL return a failure
    result indicating the connection is unavailable, without issuing any FC03
    request, and with no raw values (Requirement 1.8).

    Validates: Requirements 1.8
    """
    client = MagicMock()
    client.connect.return_value = False
    client.close.return_value = None

    gateway = PymodbusControllerGateway(
        settings=_settings_with_addresses([0, 1]),
        client_factory=lambda: client,
    )

    result = gateway.read_snapshot()

    assert result.status is ControllerReadStatus.CONNECTION_UNAVAILABLE
    assert client.read_holding_registers.call_count == 0
    assert result.raw_values == {}
    assert result.failed_addresses == ()


def test_block_error_records_failed_addresses_and_continues() -> None:
    """A block whose response isError() records its addresses and keeps going.

    When an FC03 response reports an error for a block, the affected block's
    addresses SHALL be recorded as read failures and the gateway SHALL continue
    with the remaining blocks, contributing no successful values for the failed
    block (Requirements 10.1, 1.7).

    Validates: Requirements 10.1, 1.7
    """
    # Two gapped blocks: [0, 1] (errors) and [10, 11] (succeeds).
    client = MagicMock()
    client.connect.return_value = True
    client.close.return_value = None
    client.read_holding_registers.side_effect = [
        _error_response(),
        _ok_response([111, 222]),
    ]

    gateway = PymodbusControllerGateway(
        settings=_settings_with_addresses([0, 1, 10, 11]),
        client_factory=lambda: client,
    )

    result = gateway.read_snapshot()

    assert result.status is ControllerReadStatus.OK
    # Both blocks were attempted: the error did not abort the cycle.
    assert client.read_holding_registers.call_count == 2
    # Failed block addresses recorded; no partial successful values for them.
    assert set(result.failed_addresses) == {0, 1}
    assert 0 not in result.raw_values
    assert 1 not in result.raw_values
    # Remaining block read successfully.
    assert result.raw_values == {10: 111, 11: 222}


def test_block_exception_records_failed_addresses_and_continues() -> None:
    """A ModbusException on one block records its addresses and keeps going.

    When ``read_holding_registers`` raises a ModbusException for a block, the
    affected block's addresses SHALL be recorded as read failures and the
    gateway SHALL continue with the remaining blocks (Requirement 10.2).

    Validates: Requirements 10.2
    """
    # Two gapped blocks: [0, 1] (raises) and [10, 11] (succeeds).
    client = MagicMock()
    client.connect.return_value = True
    client.close.return_value = None
    client.read_holding_registers.side_effect = [
        ModbusException("bus fault"),  # type: ignore[no-untyped-call]
        _ok_response([333, 444]),
    ]

    gateway = PymodbusControllerGateway(
        settings=_settings_with_addresses([0, 1, 10, 11]),
        client_factory=lambda: client,
    )

    result = gateway.read_snapshot()

    assert result.status is ControllerReadStatus.OK
    assert client.read_holding_registers.call_count == 2
    assert set(result.failed_addresses) == {0, 1}
    assert 0 not in result.raw_values
    assert 1 not in result.raw_values
    assert result.raw_values == {10: 333, 11: 444}


def test_inter_block_sleep_invoked_n_minus_1_times(monkeypatch: pytest.MonkeyPatch) -> None:
    """With N read blocks, the 50 ms inter-block sleep fires exactly N-1 times.

    When a read block has been read and at least one additional block remains in
    the same poll cycle, the gateway SHALL wait the inter-block delay before the
    next read. For N blocks this delay is observed N-1 times (Requirement 2.6).

    Validates: Requirements 2.6
    """
    sleep_calls: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda seconds: sleep_calls.append(seconds))

    # Three gapped blocks -> N = 3 -> expect 2 inter-block sleeps.
    client = MagicMock()
    client.connect.return_value = True
    client.close.return_value = None
    client.read_holding_registers.return_value = _ok_response([0] * 125)

    gateway = PymodbusControllerGateway(
        settings=_settings_with_addresses([0, 1, 5, 6, 10]),
        client_factory=lambda: client,
    )

    result = gateway.read_snapshot()

    assert result.status is ControllerReadStatus.OK
    assert client.read_holding_registers.call_count == 3
    assert len(sleep_calls) == 2
    assert all(seconds == INTER_BLOCK_DELAY_S for seconds in sleep_calls)
