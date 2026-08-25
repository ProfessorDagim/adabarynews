from datetime import UTC, datetime
from typing import Protocol

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import PostDraft, ScheduledPublication
from app.services.telegram_publication import TelegramPublicationService


class ScheduledPublicationWorker:
    """Deliver due drafts exactly once, preserving failures for later inspection."""

    def __init__(self, publication_service: TelegramPublicationService) -> None:
        self.publication_service = publication_service

    async def publish_due(self, session: Session, now: datetime | None = None) -> int:
        now = now or datetime.now(UTC)
        due = session.scalars(
            select(ScheduledPublication).where(
                ScheduledPublication.status == "scheduled",
                ScheduledPublication.scheduled_for <= now,
            )
        ).all()
        published = 0
        for scheduled in due:
            draft = session.get(PostDraft, scheduled.draft_id)
            if draft is None:
                scheduled.status = "failed"
                scheduled.last_error = "The associated draft no longer exists"
                continue
            scheduled.attempts += 1
            try:
                await self.publication_service.approve_and_publish(draft, session)
                scheduled.status = "published"
                scheduled.last_error = None
                published += 1
            except HTTPException as error:
                scheduled.status = "failed"
                scheduled.last_error = str(error.detail)[:1000]
        session.commit()
        return published
