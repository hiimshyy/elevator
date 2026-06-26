"""pymodbus-backed adapter implementing :class:`ControllerGatewayPort`.

This adapter reads the elevator controller's holding-register map over RS-485
using ``pymodbus``. It groups registers into the fewest contiguous FC03 read
requests (via :func:`build_read_blocks`), issues them one block at a time, and
reports the outcome through domain types only. No ``pymodbus`` type or exception
ever crosses the port boundary: per-block transport faults are recorded as
failed addresses and the connection/validation outcome is conveyed via
``ControllerReadStatus``.
"""

import logging
import time
from collections.abc import Callable

from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException

from elevator_pdm.application.services.read_block_planner import build_read_blocks
from elevator_pdm.domain.interfaces.controller_gateway import (
    ControllerGatewayPort,
    ControllerReadResult,
    ControllerReadStatus,
)
from elevator_pdm.domain.value_objects import ReadBlock, RegisterEntry, RegisterMap
from elevator_pdm.infrastructure.config.settings import Settings

logger = logging.getLogger(__name__)

#: Lowest valid Modbus unit/slave id.
MIN_SLAVE_ID = 1
#: Highest valid Modbus unit/slave id.
MAX_SLAVE_ID = 247

#: Default per-request timeout in milliseconds when none is configured.
DEFAULT_TIMEOUT_MS = 1000
#: Inclusive lower bound for the clamped per-request timeout.
MIN_TIMEOUT_MS = 100
#: Inclusive upper bound for the clamped per-request timeout.
MAX_TIMEOUT_MS = 10000

#: Delay observed between successive read blocks (seconds).
INTER_BLOCK_DELAY_S = 0.05


def clamp_timeout_ms(value_ms: int | None) -> int:
    """Clamp a configured timeout to the supported range.

    Returns :data:`DEFAULT_TIMEOUT_MS` when ``value_ms`` is ``None``; otherwise
    clamps the value into the inclusive range
    ``[MIN_TIMEOUT_MS, MAX_TIMEOUT_MS]`` (Requirement 1.6).

    Args:
        value_ms: The configured per-request timeout in milliseconds, or
            ``None`` when unset.

    Returns:
        The effective per-request timeout in milliseconds.
    """
    if value_ms is None:
        return DEFAULT_TIMEOUT_MS
    return max(MIN_TIMEOUT_MS, min(MAX_TIMEOUT_MS, value_ms))


class PymodbusControllerGateway(ControllerGatewayPort):
    """Reads controller telemetry over RS-485 Modbus RTU using ``pymodbus``.

    The serial profile, slave id, register map, and per-request timeout are all
    sourced from ``Settings.controller_telemetry`` — there are no inline
    transport literals. A ``client_factory`` may be injected to supply a custom
    or mocked :class:`ModbusSerialClient` for testing.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        client_factory: Callable[[], ModbusSerialClient] | None = None,
    ) -> None:
        self._settings = settings or Settings()
        self._client_factory = client_factory or self._build_client

    def _build_register_map(self) -> RegisterMap:
        """Build the domain register map from configured register entries."""
        entries = tuple(
            RegisterEntry(
                address=entry.address,
                key=entry.key,
                meaning=entry.meaning,
                base=entry.base,
                scale=entry.scale,
                unit=entry.unit,
            )
            for entry in self._settings.controller_telemetry.register_map
        )
        return RegisterMap(entries=entries)

    def _build_client(self) -> ModbusSerialClient:
        """Construct a ``ModbusSerialClient`` from the configured serial profile."""
        serial = self._settings.controller_telemetry.serial
        timeout_s = clamp_timeout_ms(serial.timeout_ms) / 1000.0
        return ModbusSerialClient(
            port=serial.port,
            baudrate=serial.baudrate,
            bytesize=serial.bytesize,
            parity=serial.parity,
            stopbits=serial.stopbits,
            timeout=timeout_s,
        )

    def read_snapshot(self) -> ControllerReadResult:
        """Run one controller poll cycle and return its result.

        Validates the configured slave id before any I/O, establishes the
        serial connection, plans contiguous FC03 read blocks, and issues one
        request per block. Per-block faults are recorded as failed addresses and
        never raised. See :class:`ControllerGatewayPort` for the full contract.
        """
        slave_id = self._settings.controller_telemetry.slave_id

        if not MIN_SLAVE_ID <= slave_id <= MAX_SLAVE_ID:
            logger.warning("Controller slave id %s out of range [1, 247]; skipping poll", slave_id)
            return ControllerReadResult(
                status=ControllerReadStatus.INVALID_SLAVE_ID,
                slave_id=slave_id,
                raw_values={},
                failed_addresses=(),
            )

        client = self._client_factory()
        try:
            if not client.connect():
                logger.warning("Controller serial connection unavailable; skipping poll")
                return ControllerReadResult(
                    status=ControllerReadStatus.CONNECTION_UNAVAILABLE,
                    slave_id=slave_id,
                    raw_values={},
                    failed_addresses=(),
                )

            blocks = build_read_blocks(self._build_register_map())
            raw_values, failed_addresses = self._read_blocks(client, blocks, slave_id)
            return ControllerReadResult(
                status=ControllerReadStatus.OK,
                slave_id=slave_id,
                raw_values=raw_values,
                failed_addresses=tuple(failed_addresses),
            )
        finally:
            self._safe_close(client)

    def _read_blocks(
        self,
        client: ModbusSerialClient,
        blocks: list[ReadBlock],
        slave_id: int,
    ) -> tuple[dict[int, int], list[int]]:
        """Issue an FC03 request per block, collecting raw values and failures."""
        raw_values: dict[int, int] = {}
        failed_addresses: list[int] = []
        last_index = len(blocks) - 1

        for index, block in enumerate(blocks):
            block_addresses = [entry.address for entry in block.entries]
            try:
                response = client.read_holding_registers(
                    address=block.start,
                    count=block.count,
                    device_id=slave_id,
                )
                if response.isError():
                    logger.warning(
                        "Controller FC03 error for block start=%s count=%s",
                        block.start,
                        block.count,
                    )
                    failed_addresses.extend(block_addresses)
                else:
                    for offset, address in enumerate(block_addresses):
                        raw_values[address] = response.registers[offset]
            except ModbusException as exc:
                logger.warning(
                    "Controller FC03 exception for block start=%s count=%s: %s",
                    block.start,
                    block.count,
                    exc,
                )
                failed_addresses.extend(block_addresses)

            if index != last_index:
                time.sleep(INTER_BLOCK_DELAY_S)

        return raw_values, failed_addresses

    @staticmethod
    def _safe_close(client: ModbusSerialClient) -> None:
        """Close the client, swallowing any transport error on shutdown."""
        try:
            client.close()
        except ModbusException as exc:  # pragma: no cover - defensive cleanup
            logger.debug("Error closing controller client: %s", exc)
