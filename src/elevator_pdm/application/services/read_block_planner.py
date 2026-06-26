"""Pure, side-effect-free helpers for planning Modbus read blocks and scaling.

These functions contain no I/O, no logging, and never mutate their inputs. They
are the primary targets for property-based testing per the feature design.
"""

from typing import NamedTuple

from elevator_pdm.domain.value_objects import ReadBlock, RegisterEntry, RegisterMap

#: Maximum number of registers allowed in a single FC03 read request.
MAX_REGISTERS_PER_BLOCK = 100


class ScaledValue(NamedTuple):
    """Result of applying a scale factor to a raw register value.

    ``scaled`` holds the engineering value (raw divided by the parsed divisor,
    or the raw value itself when no/invalid scale applies). ``scale_invalid`` is
    True when a non-empty scale string could not be parsed as a non-zero base-10
    integer.
    """

    scaled: float
    scale_invalid: bool


def build_read_blocks(register_map: RegisterMap) -> list[ReadBlock]:
    """Group register entries into the fewest contiguous read blocks.

    Entries are sorted by address in strictly ascending order before grouping
    (Req 2.1). The active block is extended when the next address is contiguous
    (``next == max + 1``) and the block still holds 99 or fewer registers
    (Req 2.2). A new block is started on an address gap (Req 2.3) or once the
    active block already holds exactly 100 registers (Req 2.4). No block exceeds
    100 registers and no block contains an internal address gap (Req 2.5). An
    empty register map yields zero blocks (Req 2.8).

    Args:
        register_map: The register map to plan reads for.

    Returns:
        A list of contiguous ``ReadBlock`` instances in ascending address order.
    """
    sorted_entries = sorted(register_map.entries, key=lambda entry: entry.address)
    if not sorted_entries:
        return []

    blocks: list[ReadBlock] = []
    current: list[RegisterEntry] = [sorted_entries[0]]

    for entry in sorted_entries[1:]:
        max_addr = current[-1].address
        is_contiguous = entry.address == max_addr + 1
        has_room = len(current) <= MAX_REGISTERS_PER_BLOCK - 1
        if is_contiguous and has_room:
            current.append(entry)
        else:
            blocks.append(_make_block(current))
            current = [entry]

    blocks.append(_make_block(current))
    return blocks


def _make_block(entries: list[RegisterEntry]) -> ReadBlock:
    """Build a ``ReadBlock`` from a contiguous list of entries."""
    return ReadBlock(
        start=entries[0].address,
        count=len(entries),
        entries=tuple(entries),
    )


def apply_scale(raw: int, scale: str) -> ScaledValue:
    """Apply a scale-factor string to a raw register value.

    Parses a ``/N`` base-10 integer divisor and returns the exact quotient of
    ``raw`` divided by that divisor (Req 3.3). When a non-empty scale string does
    not parse as a base-10 integer, or parses to zero, the scaled value equals
    the raw value and ``scale_invalid`` is True (Req 3.4). An empty scale string
    yields the raw value with ``scale_invalid`` False (Req 3.5).

    Args:
        raw: The raw register value.
        scale: The scale-factor string, e.g. ``"/10"`` ("" = raw, no scaling).

    Returns:
        A ``ScaledValue`` carrying the scaled value and the invalid indicator.
    """
    if scale == "":
        return ScaledValue(scaled=float(raw), scale_invalid=False)

    divisor_str = scale[1:] if scale.startswith("/") else scale
    try:
        divisor = int(divisor_str, 10)
    except ValueError:
        return ScaledValue(scaled=float(raw), scale_invalid=True)

    if divisor == 0:
        return ScaledValue(scaled=float(raw), scale_invalid=True)

    return ScaledValue(scaled=raw / divisor, scale_invalid=False)
