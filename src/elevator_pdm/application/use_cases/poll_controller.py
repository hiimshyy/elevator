"""Poll controller use case — orchestrates controller reads, persistence, queuing, and MQTT.

This module exposes ``PollControllerUseCase`` which drives a single poll cycle against
the elevator controller via ``ControllerGatewayPort``, builds a ``ControllerSnapshot``
from the raw read result, persists it, enqueues a JSON-serialisable representation to
a ``ReadingQueue``, and publishes the flat controller payload via MQTT.

Task 5.1 implements: ``__init__``, pure helper functions, and ``PollControllerResult``.
Task 5.2 implements: ``execute`` and ``run_forever`` orchestration.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from elevator_pdm.application.services.read_block_planner import apply_scale
from elevator_pdm.domain.entities.controller_snapshot import ControllerSnapshot, ErrorBlock
from elevator_pdm.domain.interfaces.controller_gateway import (
    ControllerGatewayPort,
    ControllerReadResult,
    ControllerReadStatus,
)
from elevator_pdm.domain.interfaces.controller_snapshot_repository import (
    ControllerSnapshotRepository,
)
from elevator_pdm.domain.interfaces.mqtt_publisher import MqttPublisher
from elevator_pdm.infrastructure.config.settings import (
    RegisterEntryConfig,
    Settings,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Error-block offsets (relative to each block's base address)
# Mirrors _ERROR_BLOCK_FIELDS in settings — 14 non-contiguous offsets per block.
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


# ---------------------------------------------------------------------------
# Protocol mirroring poll_sensors.ReadingQueue
# ---------------------------------------------------------------------------


class ReadingQueue(Protocol):
    """Queue port for serialised controller snapshots."""

    def enqueue(self, reading: dict) -> None: ...


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PollControllerResult:
    """Outcome of a single ``PollControllerUseCase.execute`` call.

    Attributes:
        success: True when the poll cycle completed without a fatal error.
        status: The raw ``ControllerReadStatus`` returned by the gateway.
        snapshot: The persisted snapshot, or ``None`` on fatal failure.
        failed_address_count: Number of registers that could not be read.
    """

    success: bool
    status: ControllerReadStatus
    snapshot: ControllerSnapshot | None
    failed_address_count: int


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------


def _utc_iso_z() -> str:
    """Return the current UTC time as an ISO-8601 string ending with ``Z``."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _build_scale_map(
    register_map: list[RegisterEntryConfig],
) -> dict[int, str]:
    """Build an ``address -> scale_string`` lookup from the settings register map."""
    return {entry.address: entry.scale for entry in register_map}


def build_snapshot(
    read_result: ControllerReadResult,
    elevator_id: str,
    register_map: list[RegisterEntryConfig],
) -> ControllerSnapshot:
    """Build a ``ControllerSnapshot`` from a ``ControllerReadResult``.

    Pure function — no I/O, no side effects.

    Args:
        read_result: The raw result returned by ``ControllerGatewayPort.read_snapshot``.
        elevator_id: Elevator identifier passed in from the ``execute`` call.
        register_map: List of register definitions from settings; used to resolve scale
            strings for each address.

    Returns:
        An immutable ``ControllerSnapshot`` populated with raw values, scaled values,
        error blocks, and failed addresses.
    """
    scale_map = _build_scale_map(register_map)

    raw_values: dict[int, int] = dict(read_result.raw_values)

    # Build scaled_values — apply_scale per register using its scale string.
    scaled_values: dict[int, float] = {}
    for addr, raw in raw_values.items():
        scale_str = scale_map.get(addr, "")
        sv = apply_scale(raw, scale_str)
        scaled_values[addr] = sv.scaled

    # Build six error blocks.
    error_blocks: list[ErrorBlock] = []
    for n in range(1, 7):
        base = 0x3002 + (n - 1) * 0x20
        block_addresses = {base + offset for offset in _ERROR_OFFSETS}
        block_values = {
            addr: raw_values[addr] for addr in block_addresses if addr in raw_values
        }
        error_blocks.append(ErrorBlock(index=n, values=block_values))

    return ControllerSnapshot(
        elevator_id=elevator_id,
        slave_id=read_result.slave_id,
        timestamp=_utc_iso_z(),
        raw_values=raw_values,
        scaled_values=scaled_values,
        error_blocks=tuple(error_blocks),
        failed_addresses=read_result.failed_addresses,
    )


def build_elevator_payload(snapshot: ControllerSnapshot) -> dict[str, Any]:
    """Build the flat controller MQTT payload from a snapshot.

    Maps each successfully read register address (as a base-10 decimal string) to its
    raw 16-bit integer value, and includes ``slave_id`` as an integer field.

    Args:
        snapshot: The controller snapshot to serialise.

    Returns:
        A dict ready to pass to ``MqttPublisher.publish_controller_snapshot``.
        When no registers were read the dict contains only ``{"slave_id": N}``.
    """
    payload: dict[str, Any] = {"slave_id": snapshot.slave_id}
    for addr, raw in snapshot.raw_values.items():
        payload[str(addr)] = raw
    return payload


def build_enqueue_payload(snapshot: ControllerSnapshot) -> dict[str, Any]:
    """Build the JSON-serialisable enqueue representation of a snapshot.

    Produces a dict with string-keyed address maps so it round-trips through
    ``json.dumps`` / ``json.loads`` without loss.

    Args:
        snapshot: The controller snapshot to serialise.

    Returns:
        A dict containing:
        - ``raw_values``: ``{str(addr): int, ...}``
        - ``scaled_values``: ``{str(addr): float, ...}``
        - ``slave_id``: int
        - ``timestamp``: ISO-8601 string ending with ``Z``
        - ``failed_addresses``: list of int addresses

    Raises:
        ValueError: If the resulting dict is not JSON-serialisable (should never
            occur under normal operation).
    """
    payload: dict[str, Any] = {
        "raw_values": {str(addr): raw for addr, raw in snapshot.raw_values.items()},
        "scaled_values": {str(addr): scaled for addr, scaled in snapshot.scaled_values.items()},
        "slave_id": snapshot.slave_id,
        "timestamp": snapshot.timestamp,
        "failed_addresses": list(snapshot.failed_addresses),
    }
    # Guard: ensure round-trip fidelity
    try:
        json.loads(json.dumps(payload))
    except (TypeError, ValueError) as exc:  # pragma: no cover
        raise ValueError(f"Enqueue payload is not JSON-serialisable: {exc}") from exc
    return payload


# ---------------------------------------------------------------------------
# Use-case class
# ---------------------------------------------------------------------------


class PollControllerUseCase:
    """Orchestrates a single elevator controller poll cycle.

    Responsibilities:
    1. Read raw register values via ``ControllerGatewayPort``.
    2. Build a ``ControllerSnapshot`` (scaling, error blocks, timestamp).
    3. Persist the snapshot via ``ControllerSnapshotRepository``.
    4. Enqueue a JSON-serialisable representation to ``ReadingQueue``.
    5. Publish the flat controller MQTT payload via ``MqttPublisher``.
    """

    def __init__(
        self,
        controller_gateway: ControllerGatewayPort,
        snapshot_repo: ControllerSnapshotRepository,
        reading_queue: ReadingQueue,
        mqtt_publisher: MqttPublisher,
        settings: Settings,
    ) -> None:
        self._gateway = controller_gateway
        self._snapshot_repo = snapshot_repo
        self._reading_queue = reading_queue
        self._mqtt_publisher = mqtt_publisher
        self._settings = settings

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def execute(self, elevator_id: str = "elev-001") -> PollControllerResult:
        """Run one complete controller poll cycle.

        Steps:
        1. Read raw registers via the gateway.
        2. Hard-fail on non-OK status (invalid slave id, connection unavailable).
        3. Build a ``ControllerSnapshot`` from the read result.
        4. When zero registers were read: log a warning, skip persist/enqueue,
           publish a slave_id-only payload, and return a success result.
        5. Otherwise: persist, enqueue (once), and publish — each in its own
           independent ``try/except`` so a failure in one path is logged and
           tolerated without aborting the others (R5.6, R7.5).

        Args:
            elevator_id: Identifier for the elevator being polled.

        Returns:
            ``PollControllerResult`` describing the cycle outcome.
        """
        # ----------------------------------------------------------------
        # Step 1 — read from gateway
        # ----------------------------------------------------------------
        try:
            read_result = self._gateway.read_snapshot()
        except Exception as exc:  # R6.5 containment
            logger.error("Controller gateway raised an unexpected exception: %s", exc, exc_info=True)
            return PollControllerResult(
                success=False,
                status=ControllerReadStatus.CONNECTION_UNAVAILABLE,
                snapshot=None,
                failed_address_count=0,
            )

        # ----------------------------------------------------------------
        # Step 2 — hard-fail on non-OK gateway status (R1.5, R1.8)
        # ----------------------------------------------------------------
        if read_result.status != ControllerReadStatus.OK:
            logger.error(
                "Controller poll hard-failed for elevator %s: status=%s",
                elevator_id,
                read_result.status.value,
            )
            return PollControllerResult(
                success=False,
                status=read_result.status,
                snapshot=None,
                failed_address_count=0,
            )

        # ----------------------------------------------------------------
        # Step 3 — build snapshot
        # ----------------------------------------------------------------
        register_map = self._settings.controller_telemetry.register_map
        snapshot = build_snapshot(read_result, elevator_id, register_map)

        # ----------------------------------------------------------------
        # Step 4 — zero-register cycle (R5.7, R10.4)
        # ----------------------------------------------------------------
        if not snapshot.raw_values:
            logger.warning(
                "Controller poll produced zero successful register reads for elevator %s "
                "(failed: %d addresses); skipping persist and enqueue.",
                elevator_id,
                len(snapshot.failed_addresses),
            )
            slave_id_only_payload: dict[str, Any] = {"slave_id": snapshot.slave_id}
            try:
                published = self._mqtt_publisher.publish_controller_snapshot(slave_id_only_payload)
                if not published:
                    logger.warning(
                        "MQTT publish of slave_id-only payload returned False for elevator %s",
                        elevator_id,
                    )
            except Exception as exc:
                logger.warning(
                    "MQTT publish of slave_id-only payload failed for elevator %s: %s",
                    elevator_id,
                    exc,
                )
            return PollControllerResult(
                success=True,
                status=read_result.status,
                snapshot=snapshot,
                failed_address_count=len(snapshot.failed_addresses),
            )

        # ----------------------------------------------------------------
        # Step 5a — persist within 2 s (R4.2, R4.9)
        # ----------------------------------------------------------------
        try:
            self._snapshot_repo.save(snapshot)
        except Exception as exc:
            logger.error(
                "Controller snapshot persistence failed for elevator %s: %s",
                elevator_id,
                exc,
                exc_info=True,
            )
            return PollControllerResult(
                success=False,
                status=read_result.status,
                snapshot=snapshot,
                failed_address_count=len(snapshot.failed_addresses),
            )

        # ----------------------------------------------------------------
        # Step 5b — enqueue exactly once (R7.1, R7.5)
        # ----------------------------------------------------------------
        try:
            enqueue_payload = build_enqueue_payload(snapshot)
            self._reading_queue.enqueue(enqueue_payload)
        except Exception as exc:
            logger.warning(
                "Controller snapshot enqueue failed for elevator %s (snapshot retained): %s",
                elevator_id,
                exc,
            )

        # ----------------------------------------------------------------
        # Step 5c — publish flat payload at QoS 1 (R5.1, R5.4, R5.6)
        # ----------------------------------------------------------------
        try:
            flat_payload = build_elevator_payload(snapshot)
            published = self._mqtt_publisher.publish_controller_snapshot(flat_payload)
            if not published:
                logger.warning(
                    "MQTT publish_controller_snapshot returned False for elevator %s; "
                    "snapshot retained.",
                    elevator_id,
                )
        except Exception as exc:
            logger.warning(
                "MQTT publish_controller_snapshot failed for elevator %s "
                "(snapshot retained): %s",
                elevator_id,
                exc,
            )

        return PollControllerResult(
            success=True,
            status=read_result.status,
            snapshot=snapshot,
            failed_address_count=len(snapshot.failed_addresses),
        )

    def run_forever(
        self,
        elevator_id: str = "elev-001",
        *,
        max_cycles: int | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        """Run poll cycles indefinitely, separated by the configured poll interval.

        Controller failures are fully contained: any exception that escapes
        ``execute`` is caught here so the loop continues and the existing
        field-sensor cycle (managed by a separate runner) is never disturbed
        (R6.4, R6.5).

        Args:
            elevator_id: Identifier for the elevator being polled.
            max_cycles: Stop after this many cycles when provided; ``None`` means
                run forever (useful for testing).
            sleep_fn: Injected sleep function; defaults to ``time.sleep``.
        """
        interval_s: float = float(
            self._settings.controller_telemetry.poll_interval_s
            if self._settings.controller_telemetry.poll_interval_s
            else 5  # R9.2 default
        )
        cycle = 0
        while True:
            try:
                result = self.execute(elevator_id)
                if not result.success:
                    logger.warning(
                        "Controller poll cycle %d failed for elevator %s: status=%s",
                        cycle + 1,
                        elevator_id,
                        result.status.value,
                    )
                else:
                    logger.debug(
                        "Controller poll cycle %d completed for elevator %s "
                        "(failed_addresses=%d)",
                        cycle + 1,
                        elevator_id,
                        result.failed_address_count,
                    )
            except Exception as exc:  # R6.5 — belt-and-suspenders containment
                logger.error(
                    "Unexpected exception in controller poll cycle %d for elevator %s: %s",
                    cycle + 1,
                    elevator_id,
                    exc,
                    exc_info=True,
                )

            cycle += 1
            if max_cycles is not None and cycle >= max_cycles:
                return

            sleep_fn(interval_s)
