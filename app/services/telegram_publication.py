from typing import Protocol

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import PostDraft, TelegramPublication
from app.telegram.publisher import PublishedMessage, TelegramPublisher


class DraftPublisher(Protocol):
    async def publish(self, channel_id: str, text: str) -> PublishedMessage: ...


class TelegramPublicationService:
    """Require explicit approval, publish once, then retain the Telegram message ID."""

    def __init__(self, publisher: DraftPublisher, channel_id: str) -> None:
        self.publisher = publisher
        self.channel_id = channel_id

    async def approve_and_publish(self, draft: PostDraft, session: Session) -> TelegramPublication:
        if draft.status == "published":
            raise HTTPException(status_code=409, detail="This draft has already been published")
        existing = session.scalar(
            select(TelegramPublication).where(TelegramPublication.draft_id == draft.id)
        )
        if existing:
            raise HTTPException(status_code=409, detail="This draft has already been published")

        try:
            message = await self.publisher.publish(self.channel_id, draft.post_text)
        except httpx.HTTPStatusError as error:
            status_code = error.response.status_code
            raise HTTPException(
                status_code=502,
                detail=f"Telegram rejected the publishing request (HTTP {status_code}). "
                "Check the bot token, channel ID, and that the bot is an administrator allowed to post.",
            ) from error
        except (httpx.HTTPError, ValueError) as error:
            raise HTTPException(
                status_code=502,
                detail="Telegram publishing failed before a message was confirmed. "
                "Check the bot token, channel ID, bot administrator permission, and network connection.",
            ) from error
        publication = TelegramPublication(
            draft_id=draft.id,
            channel_id=self.channel_id,
            telegram_message_id=message.message_id,
        )
        draft.status = "published"
        session.add(publication)
        session.commit()
        session.refresh(publication)
        return publication


def build_publication_service(bot_token: str | None, channel_id: str | None) -> TelegramPublicationService:
    if not bot_token or not channel_id:
        raise HTTPException(
            status_code=503,
            detail="Telegram publishing is not configured. Set values in the untracked .env file.",
        )
    return TelegramPublicationService(TelegramPublisher(bot_token), channel_id)
