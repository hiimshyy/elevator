"""Property-based tests for the read-block planner."""

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from elevator_pdm.application.services.read_block_planner import (
    MAX_REGISTERS_PER_BLOCK,
    apply_scale,
    build_read_blocks,
)
from elevator_pdm.domain.value_objects import RegisterEntry, RegisterMap


def _entry(address: int) -> RegisterEntry:
    """Build a minimal RegisterEntry for a given address."""
    return RegisterEntry(
        address=address,
        key=f"k{address}",
        meaning="",
        base=10,
        scale="",
        unit="",
    )


# Strategy producing register maps with arbitrary sets of unique addresses,
# including edge cases: empty maps, single-entry maps, and dense contiguous
# runs exceeding 100 registers.
_unique_addresses = st.one_of(
    st.just(set()),  # empty register map
    st.builds(lambda a: {a}, st.integers(min_value=0, max_value=65535)),  # single entry
    st.sets(st.integers(min_value=0, max_value=65535), min_size=0, max_size=300),
    # dense contiguous run exceeding 100 registers
    st.builds(
        lambda start, length: set(range(start, start + length)),
        st.integers(min_value=0, max_value=65000),
        st.integers(min_value=101, max_value=300),
    ),
)


# Feature: modbus-controller-telemetry, Property 1: Read-block planning covers
# every register exactly once
@given(addresses=_unique_addresses)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_read_blocks_cover_every_register_exactly_once(addresses: set[int]) -> None:
    """build_read_blocks covers every input address exactly once, no extras.

    Validates: Requirements 1.3, 2.7
    """
    register_map = RegisterMap(entries=tuple(_entry(addr) for addr in sorted(addresses)))

    blocks = build_read_blocks(register_map)

    covered: list[int] = [entry.address for block in blocks for entry in block.entries]

    # No address is covered more than once (exactly once).
    assert len(covered) == len(set(covered))
    # The set of covered addresses equals exactly the input set (no missing,
    # no extra).
    assert set(covered) == addresses


# Feature: modbus-controller-telemetry, Property 2: Read blocks respect size and
# contiguity invariants
@given(addresses=_unique_addresses)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_read_blocks_respect_size_and_contiguity(addresses: set[int]) -> None:
    """Every block holds <=100 registers and forms a contiguous run.

    Validates: Requirements 2.2, 2.3, 2.4, 2.5, 2.8
    """
    register_map = RegisterMap(entries=tuple(_entry(addr) for addr in sorted(addresses)))

    blocks = build_read_blocks(register_map)

    # Req 2.8: empty register map yields zero read blocks.
    if not addresses:
        assert blocks == []
        return

    for block in blocks:
        # Req 2.4 / 2.5: no block contains more than 100 registers, by both the
        # declared count and the actual covered entries.
        assert block.count <= MAX_REGISTERS_PER_BLOCK
        assert len(block.entries) <= MAX_REGISTERS_PER_BLOCK
        # count must agree with the number of covered entries.
        assert block.count == len(block.entries)

        covered = [entry.address for entry in block.entries]
        # Req 2.2 / 2.3 / 2.5: within a block consecutive covered addresses
        # differ by exactly 1 (no internal gap).
        for prev, nxt in zip(covered, covered[1:]):
            assert nxt - prev == 1
        # Equivalently, the addresses form a contiguous run from start to
        # start + count - 1.
        assert covered == list(range(block.start, block.start + block.count))


# Feature: modbus-controller-telemetry, Property 3: Read blocks are globally ascending
@given(addresses=_unique_addresses)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_read_blocks_are_globally_ascending(addresses: set[int]) -> None:
    """Covered addresses across all blocks, in block order, strictly ascend.

    Validates: Requirements 2.1
    """
    register_map = RegisterMap(entries=tuple(_entry(addr) for addr in sorted(addresses)))

    blocks = build_read_blocks(register_map)

    # Flatten the covered addresses across all blocks, preserving block order
    # and within-block entry order.
    covered: list[int] = [entry.address for block in blocks for entry in block.entries]

    # Req 2.1: the concatenated sequence is strictly ascending (each address is
    # strictly greater than the one before it).
    for prev, nxt in zip(covered, covered[1:]):
        assert nxt > prev


# Strategy producing scale-factor strings spanning every behavioural category:
# the empty string, valid "/N" divisors (including zero and negatives),
# arbitrary free text, and the explicit edge cases called out by the design.
_scale_strings = st.one_of(
    st.just(""),
    st.builds(lambda n: f"/{n}", st.integers(min_value=-1000, max_value=1000)),
    st.text(max_size=8),
    st.sampled_from(["", "/10", "/100", "/0", "/abc", "x10", "10", "/-5", "//10"]),
)

# Raw register values across the full 16-bit range with the boundaries 0 and
# 65535 sampled explicitly.
_raw_values = st.one_of(
    st.just(0),
    st.just(65535),
    st.integers(min_value=0, max_value=65535),
)


# Feature: modbus-controller-telemetry, Property 6: Scale application is correct
# across all scale strings
@given(raw=_raw_values, scale=_scale_strings)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_apply_scale_is_correct_across_all_scale_strings(raw: int, scale: str) -> None:
    """apply_scale divides by parsed divisors and flags invalid scale strings.

    For a non-empty scale string that parses (optionally after a leading "/")
    as a non-zero base-10 integer, the scaled value equals the exact quotient of
    raw / divisor with scale_invalid False (Req 3.3). When the string does not
    parse as a base-10 integer or parses to zero, the scaled value equals raw
    and scale_invalid is True (Req 3.4). The empty string yields raw with
    scale_invalid False (Req 3.5).

    Validates: Requirements 3.3, 3.4, 3.5
    """
    result = apply_scale(raw, scale)

    if scale == "":
        # Req 3.5: empty scale yields the raw value, never flagged invalid.
        assert result.scaled == float(raw)
        assert result.scale_invalid is False
        return

    body = scale[1:] if scale.startswith("/") else scale
    try:
        divisor = int(body, 10)
    except ValueError:
        divisor = None

    if divisor is not None and divisor != 0:
        # Req 3.3: scaled equals the exact quotient raw / divisor.
        assert result.scaled == raw / divisor
        assert result.scale_invalid is False
    else:
        # Req 3.4: unparseable or zero divisor -> raw value, flagged invalid.
        assert result.scaled == float(raw)
        assert result.scale_invalid is True
