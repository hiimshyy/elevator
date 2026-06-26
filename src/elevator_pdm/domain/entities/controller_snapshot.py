"""Elevator controller telemetry snapshot domain entity."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorBlock:
    """A single error-history block read from the controller."""

    index: int  # 1..6
    values: dict[int, int]  # address -> raw value for the block


@dataclass(frozen=True)
class ControllerSnapshot:
    """Immutable snapshot of controller registers from a single poll cycle."""

    elevator_id: str
    slave_id: int  # 1..247
    timestamp: str  # UTC ISO-8601, ends with "Z"
    raw_values: dict[int, int]  # address -> raw 16-bit unsigned
    scaled_values: dict[int, float]  # address -> scaled value
    error_blocks: tuple[ErrorBlock, ...]  # six error-history blocks
    failed_addresses: tuple[int, ...]  # addresses that failed to read
    id: int | None = None
