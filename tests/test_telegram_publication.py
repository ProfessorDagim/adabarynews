import json
from uuid import UUID

import httpx
import pytest
from fastapi import HTTPException

from app.database.models import PostDraft
from app.services.telegram_publication import TelegramPublicationService
from app.telegram.publisher import PublishedMessage, TelegramPublisher
from tests.test_article_storage import make_session


@pytest.mark.asyncio
async def test_telegram_publisher_sends_expected_bot_api_payload() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 42}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await TelegramPublisher("test-token").publish("@adabary", "Hello", client)

    assert result.message_id == 42
    assert requests[0].url.path.endswith("/bottest-token/sendMessage")
    assert json.loads(requests[0].content) == {
        "chat_id": "@adabary",
        "text": "Hello",
        "disable_web_page_preview": True,
    }


class FakePublisher:
    async def publish(self, channel_id: str, text: str) -> PublishedMessage:
        assert channel_id == "@adabary"
        assert text == "Draft text"
        return PublishedMessage(message_id=123)


class FailingPublisher:
    async def publish(self, channel_id: str, text: str) -> PublishedMessage:
        request = httpx.Request("POST", "https://api.telegram.org/botredacted/sendMessage")
        response = httpx.Response(403, request=request)
        raise httpx.HTTPStatusError("Forbidden", request=request, response=response)


@pytest.mark.asyncio
async def test_approval_publishes_once_and_records_message_id() -> None:
    session = make_session()
    draft = PostDraft(
        article_id=UUID("a6fa6778-1a0c-4769-9e16-27f6983ea4a9"),
        headline="Draft headline",
        post_text="Draft text",
        hashtags="#AI",
        status="draft",
        provider="heuristic",
    )
    session.add(draft)
    session.commit()
    service = TelegramPublicationService(FakePublisher(), "@adabary")

    publication = await service.approve_and_publish(draft, session)

    assert publication.telegram_message_id == 123
    assert draft.status == "published"
    with pytest.raises(HTTPException, match="already been published"):
        await service.approve_and_publish(draft, session)


@pytest.mark.asyncio
async def test_telegram_failure_is_a_safe_api_error_and_draft_remains_unpublished() -> None:
    session = make_session()
    draft = PostDraft(
        article_id=UUID("b6fa6778-1a0c-4769-9e16-27f6983ea4a9"),
        headline="Draft headline",
        post_text="Draft text",
        hashtags="#AI",
        status="draft",
        provider="heuristic",
    )
    session.add(draft)
    session.commit()

    with pytest.raises(HTTPException, match="HTTP 403") as error:
        await TelegramPublicationService(FailingPublisher(), "@adabary").approve_and_publish(
            draft, session
        )

    assert error.value.status_code == 502
    assert draft.status == "draft"
