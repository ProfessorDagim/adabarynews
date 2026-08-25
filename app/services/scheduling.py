from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import PostDraft, ScheduledPublication


class SchedulingService:
    """Schedule a reviewable draft once; actual delivery is controlled separately."""

    def schedule(
        self, draft: PostDraft, scheduled_for: datetime, session: Session
    ) -> ScheduledPublication:
        if draft.status == "published":
            raise HTTPException(status_code=409, detail="A published draft cannot be scheduled")
        scheduled_for = self._as_utc(scheduled_for)
        if scheduled_for <= datetime.now(UTC):
            raise HTTPException(status_code=422, detail="scheduled_for must be in the future")
        record = session.scalar(
            select(ScheduledPublication).where(ScheduledPublication.draft_id == draft.id)
        )
        if record is None:
            record = ScheduledPublication(draft_id=draft.id, scheduled_for=scheduled_for)
            session.add(record)
        else:
            record.scheduled_for = scheduled_for
            record.status = "scheduled"
            record.last_error = None
        session.commit()
        session.refresh(record)
        return record

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
