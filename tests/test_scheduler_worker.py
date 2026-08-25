from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.database.models import PostDraft, ScheduledPublication
from app.scheduler.publications import ScheduledPublicationWorker
from app.telegram.publisher import PublishedMessage
from tests.test_article_storage import make_session


class FakePublicationService:
    async def approve_and_publish(self, draft: PostDraft, session: object) -> object:
        draft.status = "published"
        return PublishedMessage(message_id=44)


@pytest.mark.asyncio
async def test_worker_publishes_a_due_draft_once() -> None:
    session = make_session()
    draft = PostDraft(
        article_id=UUID("d6fa6778-1a0c-4769-9e16-27f6983ea4a9"),
        headline="Scheduled draft",
        post_text="Draft text",
        hashtags="#AI",
        status="draft",
        provider="heuristic",
    )
    session.add(draft)
    session.commit()
    scheduled = ScheduledPublication(
        draft_id=draft.id,
        scheduled_for=datetime.now(UTC) - timedelta(minutes=1),
    )
    session.add(scheduled)
    session.commit()

    published = await ScheduledPublicationWorker(FakePublicationService()).publish_due(session)

    assert published == 1
    assert scheduled.status == "published"
    assert draft.status == "published"
