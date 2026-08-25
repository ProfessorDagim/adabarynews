from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.services.article_analysis import ArticleAnalysisService
from app.services.article_storage import ArticleStorageService
from app.services.draft_generation import DraftGenerationService
from app.services.news_collector import NewsCollectionService
from app.services.scheduling import SchedulingService
from app.services.telegram_publication import TelegramPublicationService
from app.telegram.publisher import TelegramPublisher
from app.database.models import PostDraft


def control_panel() -> dict[str, object]:
    return {"inline_keyboard": [[{"text": "🔎 Find news", "callback_data": "find"}]]}


def approval_buttons(draft_id: UUID) -> dict[str, object]:
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Publish now", "callback_data": f"approve:{draft_id}"},
                {"text": "❌ Reject", "callback_data": f"reject:{draft_id}"},
            ],
            [
                {"text": "🕐 In 1 hour", "callback_data": f"schedule:{draft_id}:60"},
                {"text": "🕒 In 3 hours", "callback_data": f"schedule:{draft_id}:180"},
            ],
        ]
    }


class OwnerControlService:
    """Run a manual owner workflow: collect, analyze, draft, then await a button action."""

    def __init__(
        self,
        news: NewsCollectionService,
        storage: ArticleStorageService,
        analysis: ArticleAnalysisService,
        drafts: DraftGenerationService,
        scheduling: SchedulingService,
        publication: TelegramPublicationService,
        bot: TelegramPublisher,
        owner_chat_id: str,
    ) -> None:
        self.news, self.storage, self.analysis, self.drafts = news, storage, analysis, drafts
        self.scheduling, self.publication, self.bot, self.owner_chat_id = scheduling, publication, bot, owner_chat_id

    async def find_news(self, session: Session, query: str, limit: int) -> int:
        articles = await self.news.collect(query, limit)
        sent = 0
        for incoming in articles:
            stored = self.storage.store([incoming], session)
            if not stored.stored:
                continue
            # The prior storage call committed the record; retrieve the stored object by URL.
            from sqlalchemy import select
            from app.database.models import Article
            article = session.scalar(select(Article).where(Article.url == str(incoming.url)))
            if article is None:
                continue
            result = await self.analysis.analyze_and_store(article, session)
            if not result.recommended:
                continue
            draft = await self.drafts.generate_and_store(article, session)
            await self.bot.send_message(self.owner_chat_id, draft.post_text, approval_buttons(draft.id))
            sent += 1
        return sent

    async def handle_callback(self, data: str, session: Session) -> str:
        parts = data.split(":")
        if data == "find":
            sent = await self.find_news(session, "artificial intelligence OR OpenAI OR ChatGPT OR AI", 10)
            return f"Found {sent} recommended draft(s) for review."
        if len(parts) < 2:
            raise HTTPException(status_code=400, detail="Unknown control action")
        draft = session.get(PostDraft, UUID(parts[1]))
        if draft is None:
            raise HTTPException(status_code=404, detail="Draft not found")
        if parts[0] == "approve":
            await self.publication.approve_and_publish(draft, session)
            return "Published to the channel."
        if parts[0] == "reject":
            draft.status = "rejected"
            session.commit()
            return "Draft rejected."
        if parts[0] == "schedule" and len(parts) == 3:
            minutes = int(parts[2])
            self.scheduling.schedule(draft, datetime.now(UTC) + timedelta(minutes=minutes), session)
            return f"Scheduled for {minutes} minutes from now."
        raise HTTPException(status_code=400, detail="Unknown control action")
