"""Register-map value objects for Modbus controller telemetry."""
from dataclasses import dataclass


@dataclass(frozen=True)
class RegisterEntry:
    """A single Modbus holding-register definition."""

    address: int  # Modbus holding-register address
    key: str  # JSON field key
    meaning: str  # human-readable description
    base: int  # display radix: 10 or 16
    scale: str  # scale factor string, e.g. "/10" ("" = raw)
    unit: str  # physical unit ("" = dimensionless)


@dataclass(frozen=True)
class RegisterMap:
    """An ordered collection of register entries."""

    entries: tuple[RegisterEntry, ...]


@dataclass(frozen=True)
class ReadBlock:
    """A contiguous block of registers to read in one Modbus request."""

    start: int
    count: int
    entries: tuple[RegisterEntry, ...]


@dataclass(frozen=True)
class RegisterValue:
    """A decoded register value, raw and scaled."""

    address: int
    raw: int
    scaled: float
    scale_invalid: bool = False
