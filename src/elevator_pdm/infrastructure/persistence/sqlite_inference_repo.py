"""SQLite implementation of InferenceRepository."""

from sqlalchemy.orm import Session

from elevator_pdm.domain.entities.inference_result import InferenceResult
from elevator_pdm.domain.interfaces.inference_repository import InferenceRepository
from elevator_pdm.infrastructure.persistence.models import InferenceResult as ORMInferenceResult


class SQLiteInferenceRepo(InferenceRepository):
    """SQLite adapter for InferenceRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _to_orm(self, result: InferenceResult) -> ORMInferenceResult:
        return ORMInferenceResult(
            elevator_id=result.elevator_id,
            timestamp=result.timestamp,
            model_name=result.model_name,
            model_version=result.model_version,
            status=result.status,
            confidence=result.confidence,
            health_score=result.health_score,
            features_json=result.features_json,
        )

    def _to_domain(self, orm_result: ORMInferenceResult) -> InferenceResult:
        return InferenceResult(
            id=orm_result.id,
            elevator_id=orm_result.elevator_id,
            timestamp=orm_result.timestamp,
            model_name=orm_result.model_name,
            model_version=orm_result.model_version,
            status=orm_result.status,
            confidence=orm_result.confidence,
            health_score=orm_result.health_score,
            features_json=orm_result.features_json,
        )

    def save(self, result: InferenceResult) -> None:
        orm_result = self._to_orm(result)
        self._session.add(orm_result)
        self._session.commit()
        self._session.refresh(orm_result)
        result.id = orm_result.id
        result.timestamp = orm_result.timestamp

    def find_by_elevator(
        self,
        elevator_id: str,
        from_ts: str | None = None,
        to_ts: str | None = None,
        status: str | None = None,
    ) -> list[InferenceResult]:
        query = self._session.query(ORMInferenceResult).filter_by(elevator_id=elevator_id)

        if from_ts:
            query = query.filter(ORMInferenceResult.timestamp >= from_ts)
        if to_ts:
            query = query.filter(ORMInferenceResult.timestamp <= to_ts)
        if status:
            query = query.filter_by(status=status)

        query = query.order_by(ORMInferenceResult.timestamp.desc())
        return [self._to_domain(result) for result in query.all()]

    def find_latest(self, elevator_id: str) -> InferenceResult | None:
        orm_result = (
            self._session.query(ORMInferenceResult)
            .filter_by(elevator_id=elevator_id)
            .order_by(ORMInferenceResult.timestamp.desc())
            .first()
        )
        return self._to_domain(orm_result) if orm_result else None
