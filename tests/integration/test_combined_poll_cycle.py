"""Integration tests for the combined poll cycle (R6.3, R6.4, R6.5).

Validates that running ``PollSensorsUseCase`` and ``PollControllerUseCase``
in the same cycle produces the expected MQTT publishes, and that a controller
failure leaves the field-sensor cycle completely intact.

Requirements covered:
- R6.3: One combined cycle publishes to ``embody/w``, ``embody/r``, and
        ``embody/elevator``.
- R6.4: A non-OK controller gateway status does not interrupt the sensor cycle.
- R6.5: A gateway exception is contained within the controller poll path and
        never propagates into the sensor cycle.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from elevator_pdm.application.use_cases.poll_controller import PollControllerUseCase
from elevator_pdm.application.use_cases.poll_sensors import PollSensorsUseCase
from elevator_pdm.domain.interfaces.controller_gateway import (
    ControllerGatewayPort,
    ControllerReadResult,
    ControllerReadStatus,
)
from elevator_pdm.infrastructure.config.settings import Settings
from elevator_pdm.infrastructure.persistence.models import Base
from elevator_pdm.infrastructure.persistence.sqlite_controller_snapshot_repo import (
    SQLiteControllerSnapshotRepo,
)
from elevator_pdm.infrastructure.persistence.sqlite_reading_repo import SQLiteReadingRepo
from elevator_pdm.infrastructure.sensors.mock_gateway import MockGateway


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _NoopQueue:
    """Drop all enqueue calls — no persistence, no external dependencies."""

    def enqueue(self, reading: dict) -> None:  # noqa: D401
        return None


def _make_in_memory_repos() -> tuple[SQLiteReadingRepo, SQLiteControllerSnapshotRepo]:
    """Create fresh in-memory SQLite repos with all tables initialised.

    Uses ``StaticPool`` so the same connection is shared across threads, and
    ``check_same_thread=False`` to satisfy SQLite's single-thread guard.
    SQLite does **not** enforce FK constraints by default, so inserting
    ``SensorReading`` rows without a matching ``elevators`` row is safe here.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    reading_repo = SQLiteReadingRepo(session)
    snapshot_repo = SQLiteControllerSnapshotRepo(session)
    return reading_repo, snapshot_repo


def _make_mock_mqtt() -> MagicMock:
    """Return a MagicMock that mimics ``MqttPublisher`` with three methods."""
    mock = MagicMock()
    mock.publish_reading.return_value = True
    mock.publish_status.return_value = True
    mock.publish_controller_snapshot.return_value = True
    return mock


def _make_ok_controller_gateway() -> ControllerGatewayPort:
    """Return a mock controller gateway that returns a healthy OK result."""
    gateway = MagicMock(spec=ControllerGatewayPort)
    gateway.read_snapshot.return_value = ControllerReadResult(
        status=ControllerReadStatus.OK,
        slave_id=1,
        raw_values={8210: 100, 8211: 200},
        failed_addresses=(),
    )
    return gateway


# ---------------------------------------------------------------------------
# Test 1 — R6.3: combined cycle publishes to all three MQTT topics
# ---------------------------------------------------------------------------


def test_combined_cycle_publishes_to_all_three_topics() -> None:
    """Running both use cases in one cycle covers all three MQTT topics (R6.3).

    ``PollSensorsUseCase`` must call ``publish_reading`` (≥1 time) and
    ``publish_status`` (exactly 1 time) to cover ``embody/w`` and ``embody/r``.
    ``PollControllerUseCase`` must call ``publish_controller_snapshot`` (exactly
    1 time) to cover ``embody/elevator``.

    Validates: Requirements 6.3
    """
    elevator_id = "elev-001"

    reading_repo, snapshot_repo = _make_in_memory_repos()
    mock_mqtt = _make_mock_mqtt()
    noop_queue = _NoopQueue()

    # Wire sensor use case with MockGateway (returns valid data for all 3 sensors)
    poll_sensors = PollSensorsUseCase(
        sensor_gateway=MockGateway(seed=42),
        reading_repo=reading_repo,
        redis_queue=noop_queue,
        mqtt_publisher=mock_mqtt,
    )

    # Wire controller use case with a mock gateway that returns OK
    poll_controller = PollControllerUseCase(
        controller_gateway=_make_ok_controller_gateway(),
        snapshot_repo=snapshot_repo,
        reading_queue=noop_queue,
        mqtt_publisher=mock_mqtt,
        settings=Settings(),
    )

    # Execute both use cases in the same combined cycle
    sensor_result = poll_sensors.execute(elevator_id)
    controller_result = poll_controller.execute(elevator_id)

    # --- R6.3 assertions ---

    # embody/w: at least one reading published (one per successful sensor read,
    # up to 3 for vibration + temp/humidity + load)
    assert mock_mqtt.publish_reading.call_count >= 1, (
        f"Expected at least 1 publish_reading call (embody/w); "
        f"got {mock_mqtt.publish_reading.call_count}"
    )

    # embody/r: exactly one status summary published per sensor cycle
    assert mock_mqtt.publish_status.call_count == 1, (
        f"Expected exactly 1 publish_status call (embody/r); "
        f"got {mock_mqtt.publish_status.call_count}"
    )

    # embody/elevator: exactly one controller snapshot published
    assert mock_mqtt.publish_controller_snapshot.call_count == 1, (
        f"Expected exactly 1 publish_controller_snapshot call (embody/elevator); "
        f"got {mock_mqtt.publish_controller_snapshot.call_count}"
    )

    # Sanity: both use cases succeeded
    assert len(sensor_result["success"]) >= 1, "At least one sensor should succeed via MockGateway"
    assert controller_result.success is True, "Controller use case should succeed with OK gateway"


# ---------------------------------------------------------------------------
# Test 2 — R6.4 / R6.5: controller failure leaves sensor cycle intact
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "failure_label,gateway_factory",
    [
        (
            "non_ok_status",
            lambda: _make_connection_unavailable_gateway(),
        ),
        (
            "gateway_raises_exception",
            lambda: _make_raising_gateway(),
        ),
    ],
    ids=["non_ok_status", "gateway_raises_exception"],
)
def test_controller_poll_failure_leaves_sensor_cycle_intact(
    failure_label: str,
    gateway_factory,
) -> None:
    """Controller failure must not interrupt the field-sensor poll cycle (R6.4, R6.5).

    Two failure modes are exercised:
    - **Failure mode A** — non-OK gateway status (``CONNECTION_UNAVAILABLE``):
      The controller use case returns ``success=False`` without raising.
    - **Failure mode B** — gateway raises ``RuntimeError``:
      The exception is contained within the controller poll path; the sensor
      cycle completes normally.

    In both cases the sensor use case must:
    - not raise an exception,
    - report at least one successful sensor read,
    - call ``publish_reading`` at least once (``embody/w``),
    - call ``publish_status`` exactly once (``embody/r``),
    - NOT call ``publish_controller_snapshot`` (no controller data to publish).

    Validates: Requirements 6.4, 6.5
    """
    elevator_id = "elev-001"

    reading_repo, snapshot_repo = _make_in_memory_repos()
    mock_mqtt = _make_mock_mqtt()
    noop_queue = _NoopQueue()

    failing_controller_gateway = gateway_factory()

    poll_sensors = PollSensorsUseCase(
        sensor_gateway=MockGateway(seed=7),
        reading_repo=reading_repo,
        redis_queue=noop_queue,
        mqtt_publisher=mock_mqtt,
    )

    poll_controller = PollControllerUseCase(
        controller_gateway=failing_controller_gateway,
        snapshot_repo=snapshot_repo,
        reading_queue=noop_queue,
        mqtt_publisher=mock_mqtt,
        settings=Settings(),
    )

    # Run controller first (will fail), then sensor (must succeed regardless)
    controller_result = poll_controller.execute(elevator_id)

    # The sensor cycle must not raise, even after a controller failure
    sensor_result = poll_sensors.execute(elevator_id)

    # --- R6.4 / R6.5 sensor-cycle assertions ---

    assert len(sensor_result["success"]) >= 1, (
        f"[{failure_label}] At least one sensor should succeed via MockGateway; "
        f"got success={sensor_result['success']}"
    )

    assert mock_mqtt.publish_reading.call_count >= 1, (
        f"[{failure_label}] Expected at least 1 publish_reading call (embody/w); "
        f"got {mock_mqtt.publish_reading.call_count}"
    )

    assert mock_mqtt.publish_status.call_count == 1, (
        f"[{failure_label}] Expected exactly 1 publish_status call (embody/r); "
        f"got {mock_mqtt.publish_status.call_count}"
    )

    # No controller data — publish_controller_snapshot must NOT have been called
    assert mock_mqtt.publish_controller_snapshot.call_count == 0, (
        f"[{failure_label}] Expected 0 publish_controller_snapshot calls on failure; "
        f"got {mock_mqtt.publish_controller_snapshot.call_count}"
    )

    # Controller result must indicate failure (not raise)
    assert controller_result.success is False, (
        f"[{failure_label}] Controller use case should report success=False on failure; "
        f"got success={controller_result.success}"
    )


# ---------------------------------------------------------------------------
# Gateway factories for failure-mode parametrize
# ---------------------------------------------------------------------------


def _make_connection_unavailable_gateway() -> ControllerGatewayPort:
    """Return a gateway that responds with CONNECTION_UNAVAILABLE (failure mode A)."""
    gateway = MagicMock(spec=ControllerGatewayPort)
    gateway.read_snapshot.return_value = ControllerReadResult(
        status=ControllerReadStatus.CONNECTION_UNAVAILABLE,
        slave_id=1,
        raw_values={},
        failed_addresses=(),
    )
    return gateway


def _make_raising_gateway() -> ControllerGatewayPort:
    """Return a gateway whose read_snapshot raises RuntimeError (failure mode B)."""
    gateway = MagicMock(spec=ControllerGatewayPort)
    gateway.read_snapshot.side_effect = RuntimeError("simulated serial fault")
    return gateway
