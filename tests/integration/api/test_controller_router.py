"""Integration tests for GET /api/elevators/{elevator_id}/controller-snapshots.

Validates Requirements 11.1 (newest-first ordering), 11.2 (time-range filtering),
and 11.3 (data sourced from the repository, not MQTT).

Each test uses a fresh in-memory SQLite database via dependency overrides so
no file-system state is shared between runs.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from elevator_pdm.domain.entities.controller_snapshot import ControllerSnapshot, ErrorBlock
from elevator_pdm.infrastructure.persistence.models import Base
from elevator_pdm.infrastructure.persistence.sqlite_controller_snapshot_repo import (
    SQLiteControllerSnapshotRepo,
)
from elevator_pdm.presentation.api.auth import verify_api_key
from elevator_pdm.presentation.api.dependencies import get_controller_snapshot_repository
from elevator_pdm.presentation.api.main import create_app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_test_repo() -> SQLiteControllerSnapshotRepo:
    """Return a fresh in-memory SQLiteControllerSnapshotRepo.

    Uses StaticPool + check_same_thread=False so the connection is shared
    between the test thread and FastAPI's worker threads.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    return SQLiteControllerSnapshotRepo(session)


def _make_snapshot(
    elevator_id: str,
    timestamp: str,
    slave_id: int = 1,
    raw_values: dict[int, int] | None = None,
) -> ControllerSnapshot:
    """Build a minimal :class:`ControllerSnapshot` suitable for testing."""
    return ControllerSnapshot(
        elevator_id=elevator_id,
        slave_id=slave_id,
        timestamp=timestamp,
        raw_values=raw_values or {8210: 100},
        scaled_values={8210: 10.0},
        error_blocks=tuple(ErrorBlock(index=i, values={}) for i in range(1, 7)),
        failed_addresses=(),
        id=None,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client_with_repo() -> tuple[TestClient, SQLiteControllerSnapshotRepo]:
    """Create a TestClient with dependency overrides for auth and the repo."""
    repo = _make_test_repo()
    app = create_app()
    app.dependency_overrides[get_controller_snapshot_repository] = lambda: repo
    app.dependency_overrides[verify_api_key] = lambda: "test-key"
    client = TestClient(app)
    return client, repo


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_returns_snapshots_newest_first(
    client_with_repo: tuple[TestClient, SQLiteControllerSnapshotRepo],
) -> None:
    """Persisted snapshots are returned newest-first (R11.1).

    Three snapshots with distinct timestamps are saved in arbitrary order;
    the API must return them sorted descending by timestamp.

    Validates: Requirements 11.1
    """
    client, repo = client_with_repo
    elevator_id = "elev-order-test"

    timestamps = [
        "2025-06-01T10:00:00Z",
        "2025-06-01T08:00:00Z",
        "2025-06-01T12:00:00Z",
    ]
    for ts in timestamps:
        repo.save(_make_snapshot(elevator_id, ts))

    response = client.get(f"/api/elevators/{elevator_id}/controller-snapshots")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 3

    returned_timestamps = [item["timestamp"] for item in body]
    # Must be in strictly descending order
    assert returned_timestamps == sorted(returned_timestamps, reverse=True), (
        f"Timestamps not newest-first: {returned_timestamps}"
    )
    # The first item must be the lexicographically latest timestamp
    assert returned_timestamps[0] == max(timestamps)


def test_time_range_filtering(
    client_with_repo: tuple[TestClient, SQLiteControllerSnapshotRepo],
) -> None:
    """Time-range query params filter results to the requested window (R11.2).

    Three snapshots (2024, 2025, 2026) are saved; the request selects only
    the window that includes 2025, so exactly one result is expected.

    Validates: Requirements 11.2
    """
    client, repo = client_with_repo
    elevator_id = "elev-filter-test"

    repo.save(_make_snapshot(elevator_id, "2024-01-01T00:00:00Z"))
    repo.save(_make_snapshot(elevator_id, "2025-06-15T12:00:00Z"))
    repo.save(_make_snapshot(elevator_id, "2026-12-31T23:59:59Z"))

    response = client.get(
        f"/api/elevators/{elevator_id}/controller-snapshots",
        params={
            "from_time": "2025-01-01T00:00:00",
            "to_time": "2025-12-31T23:59:59",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1, f"Expected 1 result after filtering, got {len(body)}"
    assert "2025" in body[0]["timestamp"]


def test_sources_data_from_repository_not_mqtt(
    client_with_repo: tuple[TestClient, SQLiteControllerSnapshotRepo],
) -> None:
    """Response payload matches what was persisted in the repository (R11.3).

    Since we control exactly what is in the repo and bypass MQTT entirely,
    matching values prove the data originates from the repository.

    Validates: Requirements 11.3
    """
    client, repo = client_with_repo
    elevator_id = "elev-source-test"
    expected_raw = {8210: 42, 8211: 99}
    expected_slave_id = 7
    expected_timestamp = "2025-03-20T09:30:00Z"

    repo.save(
        _make_snapshot(
            elevator_id,
            expected_timestamp,
            slave_id=expected_slave_id,
            raw_values=expected_raw,
        )
    )

    response = client.get(f"/api/elevators/{elevator_id}/controller-snapshots")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1

    item = body[0]
    assert item["slave_id"] == expected_slave_id
    assert item["timestamp"] == expected_timestamp
    # raw_values keys are serialised as strings in the JSON response
    assert item["raw_values"] == {str(k): v for k, v in expected_raw.items()}


def test_empty_elevator_returns_empty_list(
    client_with_repo: tuple[TestClient, SQLiteControllerSnapshotRepo],
) -> None:
    """Requesting snapshots for an elevator with no data returns 200 + [].

    Validates: Requirements 11.1
    """
    client, _ = client_with_repo

    response = client.get("/api/elevators/elev-no-data/controller-snapshots")

    assert response.status_code == 200
    assert response.json() == []


def test_limit_param_is_respected(
    client_with_repo: tuple[TestClient, SQLiteControllerSnapshotRepo],
) -> None:
    """The ``limit`` query param caps the number of returned snapshots.

    Five snapshots are persisted; requesting ``limit=2`` must return exactly
    two items (the two newest).

    Validates: Requirements 11.1, 11.2
    """
    client, repo = client_with_repo
    elevator_id = "elev-limit-test"

    timestamps = [
        "2025-01-01T00:00:00Z",
        "2025-02-01T00:00:00Z",
        "2025-03-01T00:00:00Z",
        "2025-04-01T00:00:00Z",
        "2025-05-01T00:00:00Z",
    ]
    for ts in timestamps:
        repo.save(_make_snapshot(elevator_id, ts))

    response = client.get(
        f"/api/elevators/{elevator_id}/controller-snapshots",
        params={"limit": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2, f"Expected 2 results with limit=2, got {len(body)}"

    # The two results must be the two newest timestamps
    returned_timestamps = [item["timestamp"] for item in body]
    assert returned_timestamps[0] == "2025-05-01T00:00:00Z"
    assert returned_timestamps[1] == "2025-04-01T00:00:00Z"
