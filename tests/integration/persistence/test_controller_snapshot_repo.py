"""Integration property tests for SQLiteControllerSnapshotRepo.

Uses an in-memory SQLite database so no file-system state is shared between
test runs.  Each test function gets its own fresh engine + session via the
``repo`` fixture, which is function-scoped.
"""

from __future__ import annotations

import json

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from elevator_pdm.domain.entities.controller_snapshot import (
    ControllerSnapshot,
    ErrorBlock,
)
from elevator_pdm.infrastructure.persistence.models import Base
from elevator_pdm.infrastructure.persistence.sqlite_controller_snapshot_repo import (
    SQLiteControllerSnapshotRepo,
)


# ---------------------------------------------------------------------------
# Helpers / strategies
# ---------------------------------------------------------------------------

def _make_engine_and_repo() -> tuple:
    """Create a fresh in-memory SQLite repo for one test run."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    repo = SQLiteControllerSnapshotRepo(session)
    return repo, session


# Strategy producing a dict of {int address: int raw_value (0..65535)}
_raw_values_st = st.dictionaries(
    keys=st.integers(min_value=0, max_value=65535),
    values=st.integers(min_value=0, max_value=65535),
    min_size=0,
    max_size=30,
)

# Strategy producing a dict of {int address: float scaled}
_scaled_values_st = st.dictionaries(
    keys=st.integers(min_value=0, max_value=65535),
    values=st.floats(allow_nan=False, allow_infinity=False, min_value=-1e9, max_value=1e9),
    min_size=0,
    max_size=30,
)

# Strategy producing exactly six ErrorBlock instances (index 1..6)
_error_blocks_st = st.builds(
    lambda *blocks: tuple(blocks),
    *[
        st.builds(
            lambda idx, values: ErrorBlock(
                index=idx,
                values={int(k): int(v) for k, v in values.items()},
            ),
            st.just(i),
            st.dictionaries(
                keys=st.integers(min_value=0, max_value=65535),
                values=st.integers(min_value=0, max_value=65535),
                min_size=0,
                max_size=5,
            ),
        )
        for i in range(1, 7)
    ],
)

# Strategy producing a tuple of failed addresses
_failed_addresses_st = st.lists(
    st.integers(min_value=0, max_value=65535),
    min_size=0,
    max_size=10,
    unique=True,
).map(tuple)

# Strategy producing a UTC ISO-8601 timestamp string ending with "Z"
_timestamp_st = st.builds(
    lambda y, mo, d, h, mi, s: f"{y:04d}-{mo:02d}-{d:02d}T{h:02d}:{mi:02d}:{s:02d}Z",
    st.integers(min_value=2020, max_value=2035),
    st.integers(min_value=1, max_value=12),
    st.integers(min_value=1, max_value=28),  # safe upper bound for all months
    st.integers(min_value=0, max_value=23),
    st.integers(min_value=0, max_value=59),
    st.integers(min_value=0, max_value=59),
)

# Strategy producing a valid slave_id (1..247)
_slave_id_st = st.integers(min_value=1, max_value=247)

# Full ControllerSnapshot strategy (id=None, as it is assigned by the DB)
_snapshot_st = st.builds(
    ControllerSnapshot,
    elevator_id=st.just("elev-integ-001"),
    slave_id=_slave_id_st,
    timestamp=_timestamp_st,
    raw_values=_raw_values_st,
    scaled_values=_scaled_values_st,
    error_blocks=_error_blocks_st,
    failed_addresses=_failed_addresses_st,
    id=st.none(),
)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def repo():
    """Provide a fresh in-memory SQLiteControllerSnapshotRepo."""
    r, _session = _make_engine_and_repo()
    return r


# ---------------------------------------------------------------------------
# Property 9: Persistence round-trip preserves snapshot data
# ---------------------------------------------------------------------------

# Feature: modbus-controller-telemetry, Property 9: Persistence round-trip
# preserves snapshot data
@given(snapshot=_snapshot_st)
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_persistence_round_trip_preserves_snapshot_data(snapshot: ControllerSnapshot) -> None:
    """Saving a ControllerSnapshot and reading it back yields equivalent data.

    Specifically:
    - raw_values (address → raw 16-bit unsigned) are preserved
    - scaled_values (address → float) are preserved
    - all six error_blocks (index + address→value map) are preserved
    - slave_id and timestamp are preserved

    Each Hypothesis example creates its own isolated in-memory repo so
    there is no cross-example state.

    # Feature: modbus-controller-telemetry, Property 9: Persistence round-trip
    # preserves snapshot data
    Validates: Requirements 4.3, 4.4, 4.5, 4.8
    """
    # Fresh repo per Hypothesis example — avoids cross-example contamination.
    repo, _session = _make_engine_and_repo()

    # ---- save -----------------------------------------------------------------
    repo.save(snapshot)

    # ---- read back via find_latest -------------------------------------------
    restored = repo.find_latest(snapshot.elevator_id)

    assert restored is not None, "find_latest returned None after a successful save"

    # DB assigns an auto-increment id, so we only verify it is set.
    assert restored.id is not None

    # ---- Core round-trip assertions (R4.3, R4.4, R4.5, R4.8) ----------------

    # slave_id is preserved.
    assert restored.slave_id == snapshot.slave_id

    # timestamp is preserved exactly (UTC ISO-8601 "Z" designator).
    assert restored.timestamp == snapshot.timestamp

    # raw_values round-trip: integer address keys and integer raw values.
    assert restored.raw_values == snapshot.raw_values, (
        f"raw_values mismatch:\n  original={snapshot.raw_values}\n  restored={restored.raw_values}"
    )

    # scaled_values round-trip: integer address keys and float scaled values.
    # JSON serialisation uses finite floats only (strategy excludes NaN/inf).
    assert restored.scaled_values == snapshot.scaled_values, (
        f"scaled_values mismatch:\n  original={snapshot.scaled_values}\n"
        f"  restored={restored.scaled_values}"
    )

    # error_blocks round-trip: all six blocks are present with their values.
    assert len(restored.error_blocks) == len(snapshot.error_blocks), (
        "error_blocks count changed after round-trip"
    )
    for orig_eb, rest_eb in zip(snapshot.error_blocks, restored.error_blocks):
        assert rest_eb.index == orig_eb.index, (
            f"ErrorBlock index changed: {orig_eb.index} → {rest_eb.index}"
        )
        assert rest_eb.values == orig_eb.values, (
            f"ErrorBlock[{orig_eb.index}] values mismatch:\n"
            f"  original={orig_eb.values}\n  restored={rest_eb.values}"
        )

    # failed_addresses round-trip (order-insensitive).
    assert set(restored.failed_addresses) == set(snapshot.failed_addresses), (
        f"failed_addresses mismatch:\n  original={snapshot.failed_addresses}\n"
        f"  restored={restored.failed_addresses}"
    )

    # ---- JSON serialisability of stored payload (R4.8) ----------------------
    # Verify the values can survive a JSON round-trip as the design requires.
    raw_rt = json.loads(
        json.dumps({str(k): v for k, v in snapshot.raw_values.items()})
    )
    assert {int(k): int(v) for k, v in raw_rt.items()} == snapshot.raw_values

    scaled_rt = json.loads(
        json.dumps({str(k): v for k, v in snapshot.scaled_values.items()})
    )
    assert {int(k): float(v) for k, v in scaled_rt.items()} == snapshot.scaled_values


# ---------------------------------------------------------------------------
# Property 10: Snapshot queries return newest-first
# ---------------------------------------------------------------------------

# Reusable strategy that generates a list of 2..10 *distinct* ISO-8601
# timestamps so the ordering is unambiguous.
_distinct_timestamps_st = st.lists(
    _timestamp_st,
    min_size=2,
    max_size=10,
    unique=True,
)


@given(timestamps=_distinct_timestamps_st)
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_snapshot_queries_return_newest_first(timestamps: list[str]) -> None:
    """Querying by elevator id returns all snapshots ordered newest → oldest.

    For any set of persisted snapshots with distinct timestamps, both
    ``find_by_elevator`` and ``find_latest`` must respect descending
    timestamp order.

    # Feature: modbus-controller-telemetry, Property 10: Snapshot queries
    # return newest-first
    Validates: Requirements 4.7
    """
    # Fresh repo per Hypothesis example — avoids cross-example contamination.
    repo, _session = _make_engine_and_repo()

    elevator_id = "elev-order-test"

    # Persist one minimal snapshot per generated timestamp (insertion order
    # is deliberately shuffled via iteration — Hypothesis controls that).
    saved: list[ControllerSnapshot] = []
    for ts in timestamps:
        snap = ControllerSnapshot(
            elevator_id=elevator_id,
            slave_id=1,
            timestamp=ts,
            raw_values={},
            scaled_values={},
            error_blocks=tuple(
                ErrorBlock(index=i, values={}) for i in range(1, 7)
            ),
            failed_addresses=(),
            id=None,
        )
        repo.save(snap)
        saved.append(snap)

    # ---- find_by_elevator ordering check (R4.7) -----------------------------
    results = repo.find_by_elevator(elevator_id)

    assert len(results) == len(timestamps), (
        f"Expected {len(timestamps)} results, got {len(results)}"
    )

    returned_timestamps = [r.timestamp for r in results]

    # Verify strictly descending: each timestamp must be >= the next.
    for i in range(len(returned_timestamps) - 1):
        assert returned_timestamps[i] >= returned_timestamps[i + 1], (
            f"Ordering violated at position {i}: "
            f"{returned_timestamps[i]!r} is not >= {returned_timestamps[i + 1]!r}"
        )

    # The first result must be the lexicographically largest timestamp
    # (ISO-8601 "Z" strings sort correctly as plain strings).
    expected_newest = max(timestamps)
    assert returned_timestamps[0] == expected_newest, (
        f"First result timestamp {returned_timestamps[0]!r} != "
        f"expected newest {expected_newest!r}"
    )

    # ---- find_latest picks the single newest snapshot (R4.7) ----------------
    latest = repo.find_latest(elevator_id)

    assert latest is not None, "find_latest returned None after saves"
    assert latest.timestamp == expected_newest, (
        f"find_latest timestamp {latest.timestamp!r} != "
        f"expected newest {expected_newest!r}"
    )
