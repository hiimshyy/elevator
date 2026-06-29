"""SQLite implementation of ControllerSnapshotRepository."""

import json
from typing import Any

from sqlalchemy.orm import Session

from elevator_pdm.domain.entities.controller_snapshot import ControllerSnapshot, ErrorBlock
from elevator_pdm.domain.interfaces.controller_snapshot_repository import (
    ControllerSnapshotRepository,
)
from elevator_pdm.infrastructure.persistence.models import ControllerSnapshotRow


class SQLiteControllerSnapshotRepo(ControllerSnapshotRepository):
    """SQLite adapter for ControllerSnapshotRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    def _to_orm(self, snapshot: ControllerSnapshot) -> ControllerSnapshotRow:
        """Convert a domain ControllerSnapshot to an ORM row.

        JSON serialisation rules:
        - ``raw_values`` / ``scaled_values``: JSON requires string keys, so
          int addresses are serialised as ``{str(addr): value}``.
        - ``error_blocks``: serialised as a list of
          ``{"index": n, "values": {str(addr): raw}}``.
        - ``failed_addresses``: serialised as a plain list of ints.
        """
        raw_json = json.dumps({str(addr): v for addr, v in snapshot.raw_values.items()})
        scaled_json = json.dumps({str(addr): v for addr, v in snapshot.scaled_values.items()})
        error_blocks_json = json.dumps(
            [
                {
                    "index": eb.index,
                    "values": {str(k): v for k, v in eb.values.items()},
                }
                for eb in snapshot.error_blocks
            ]
        )
        failed_json = json.dumps(list(snapshot.failed_addresses))

        return ControllerSnapshotRow(
            id=snapshot.id,
            elevator_id=snapshot.elevator_id,
            slave_id=snapshot.slave_id,
            timestamp=snapshot.timestamp,
            raw_values_json=raw_json,
            scaled_values_json=scaled_json,
            error_blocks_json=error_blocks_json,
            failed_addresses_json=failed_json,
        )

    def _to_domain(self, row: ControllerSnapshotRow) -> ControllerSnapshot:
        """Convert an ORM row back to a domain ControllerSnapshot.

        JSON deserialisation rules:
        - ``raw_values`` / ``scaled_values``: string keys are converted back to
          ``int`` addresses.
        - ``error_blocks``: each dict is reconstructed as an ``ErrorBlock``
          with ``int`` address keys in ``values``.
        - ``failed_addresses``: restored as ``tuple[int, ...]``.
        """
        raw_values: dict[int, int] = {
            int(k): int(v) for k, v in json.loads(row.raw_values_json).items()
        }
        scaled_values: dict[int, float] = {
            int(k): float(v) for k, v in json.loads(row.scaled_values_json).items()
        }
        error_blocks_data: list[Any] = json.loads(row.error_blocks_json)
        error_blocks = tuple(
            ErrorBlock(
                index=int(eb["index"]),
                values={int(k): int(v) for k, v in eb["values"].items()},
            )
            for eb in error_blocks_data
        )
        failed_addresses: tuple[int, ...] = tuple(
            int(a) for a in json.loads(row.failed_addresses_json)
        )

        return ControllerSnapshot(
            id=row.id,
            elevator_id=row.elevator_id,
            slave_id=row.slave_id,
            timestamp=row.timestamp,
            raw_values=raw_values,
            scaled_values=scaled_values,
            error_blocks=error_blocks,
            failed_addresses=failed_addresses,
        )

    # ------------------------------------------------------------------
    # Repository interface
    # ------------------------------------------------------------------

    def save(self, snapshot: ControllerSnapshot) -> None:
        """Persist a single controller snapshot.

        Uses a try/except/rollback pattern so a persistence failure leaves no
        partial row written (R4.9).
        """
        orm_row = self._to_orm(snapshot)
        try:
            self._session.add(orm_row)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

    def find_by_elevator(
        self,
        elevator_id: str,
        from_ts: str | None = None,
        to_ts: str | None = None,
        limit: int = 500,
    ) -> list[ControllerSnapshot]:
        """Query controller snapshots for an elevator, newest first (R4.7).

        Returns an empty list when no rows exist for the elevator (R4.10).
        The effective limit is capped at 500.
        """
        effective_limit = min(limit, 500)

        query = self._session.query(ControllerSnapshotRow).filter_by(
            elevator_id=elevator_id
        )

        if from_ts is not None:
            query = query.filter(ControllerSnapshotRow.timestamp >= from_ts)
        if to_ts is not None:
            query = query.filter(ControllerSnapshotRow.timestamp <= to_ts)

        query = (
            query.order_by(ControllerSnapshotRow.timestamp.desc()).limit(effective_limit)
        )

        return [self._to_domain(row) for row in query.all()]

    def find_latest(self, elevator_id: str) -> ControllerSnapshot | None:
        """Get the most recent controller snapshot for an elevator.

        Returns ``None`` when no snapshot exists (no exception raised).
        """
        row = (
            self._session.query(ControllerSnapshotRow)
            .filter_by(elevator_id=elevator_id)
            .order_by(ControllerSnapshotRow.timestamp.desc())
            .first()
        )
        return self._to_domain(row) if row is not None else None
