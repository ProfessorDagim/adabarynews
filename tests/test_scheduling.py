from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi import HTTPException

from app.database.models import PostDraft
from app.services.scheduling import SchedulingService
from tests.test_article_storage import make_session


def make_draft(session: object) -> PostDraft:
    draft = PostDraft(
        article_id=UUID("c6fa6778-1a0c-4769-9e16-27f6983ea4a9"),
        headline="Scheduled draft",
        post_text="Draft text",
        hashtags="#AI",
        status="draft",
        provider="heuristic",
    )
    session.add(draft)
    session.commit()
    return draft


def test_scheduling_creates_and_updates_a_single_publication() -> None:
    session = make_session()
    draft = make_draft(session)
    service = SchedulingService()
    first = service.schedule(draft, datetime.now(UTC) + timedelta(hours=1), session)
    updated = service.schedule(draft, datetime.now(UTC) + timedelta(hours=2), session)

    assert first.id == updated.id
    assert updated.status == "scheduled"


def test_scheduling_rejects_past_time() -> None:
    session = make_session()
    with pytest.raises(HTTPException, match="future"):
        SchedulingService().schedule(make_draft(session), datetime.now(UTC) - timedelta(minutes=1), session)
