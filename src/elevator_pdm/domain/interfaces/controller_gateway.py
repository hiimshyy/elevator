"""Controller gateway interface (port) and read-result types."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class ControllerReadStatus(Enum):
    """Outcome of a controller poll cycle.

    Members:
        OK: The poll cycle ran (individual blocks may still have failed).
        INVALID_SLAVE_ID: The configured slave id is outside the valid range.
        CONNECTION_UNAVAILABLE: The serial connection could not be established.
    """

    OK = "OK"
    INVALID_SLAVE_ID = "INVALID_SLAVE_ID"
    CONNECTION_UNAVAILABLE = "CONNECTION_UNAVAILABLE"


@dataclass(frozen=True)
class ControllerReadResult:
    """Result of a single controller poll cycle.

    Attributes:
        status: Overall outcome of the poll cycle.
        slave_id: Modbus slave id that was polled.
        raw_values: Mapping of register address to raw holding-register value.
        failed_addresses: Addresses whose read block faulted during the cycle.
    """

    status: ControllerReadStatus
    slave_id: int
    raw_values: dict[int, int]
    failed_addresses: tuple[int, ...]


class ControllerGatewayPort(ABC):
    """Abstract interface for reading elevator controller telemetry.

    Infrastructure layer provides concrete implementations (e.g. a pymodbus
    serial gateway). The port exposes only domain types and stays free of any
    Modbus library or outward-layer dependencies.
    """

    @abstractmethod
    def read_snapshot(self) -> ControllerReadResult:
        """Run one controller poll cycle and return its result.

        Executes a single poll cycle across the configured holding-register
        read blocks. Per-block Modbus faults are recorded in
        ``failed_addresses`` and never raised; the method returns a
        ``ControllerReadResult`` instead of propagating transport errors.
        """
        ...
