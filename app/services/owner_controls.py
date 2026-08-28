from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.article_analysis import ArticleAnalysisService
from app.services.article_storage import ArticleStorageService
from app.services.draft_generation import DraftGenerationService
from app.services.news_collector import NewsCollectionService
from app.services.scheduling import SchedulingService
from app.services.telegram_publication import TelegramPublicationService
from app.telegram.publisher import TelegramPublisher
from app.database.models import Article, ArticleAnalysis, PostDraft


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

    async def find_news(
        self,
        session: Session,
        query: str,
        limit: int,
        timeout_seconds: float | None = None,
        fallback_minimum_score: int = 40,
    ) -> int:
        articles = await self.news.collect(query, limit, timeout_seconds)
        candidates: list[tuple[Article, ArticleAnalysis]] = []
        for incoming in articles:
            self.storage.store([incoming], session)
            # Stored articles remain useful candidates until they receive a draft.
            article = session.scalar(select(Article).where(Article.url == str(incoming.url)))
            if article is None:
                continue
            if session.scalar(select(PostDraft).where(PostDraft.article_id == article.id)) is not None:
                continue
            result = await self.analysis.analyze_and_store(article, session)
            candidates.append((article, result))

        recommended = [(article, analysis) for article, analysis in candidates if analysis.recommended]
        if not recommended:
            # When no newly collected story clears the strict threshold, offer the best
            # undrafted story already known to the editorial database. This makes the
            # owner workflow useful on quiet news days without ever reposting a draft.
            fallback = session.execute(
                select(Article, ArticleAnalysis)
                .join(ArticleAnalysis, ArticleAnalysis.article_id == Article.id)
                .outerjoin(PostDraft, PostDraft.article_id == Article.id)
                .where(PostDraft.id.is_(None), ArticleAnalysis.final_score >= fallback_minimum_score)
                .order_by(ArticleAnalysis.final_score.desc())
                .limit(1)
            ).first()
            if fallback is not None:
                article, analysis = fallback
                analysis.recommended = True
                session.commit()
                recommended = [(article, analysis)]

        sent = 0
        for article, _ in recommended:
            draft = await self.drafts.generate_and_store(article, session)
            await self.bot.send_message(self.owner_chat_id, draft.post_text, approval_buttons(draft.id))
            sent += 1
        return sent

    async def handle_callback(self, data: str, session: Session) -> str:
        parts = data.split(":")
        if data == "find":
            sent = await self.find_news(session, "artificial intelligence OR OpenAI OR ChatGPT OR AI", 5, 6.0)
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
