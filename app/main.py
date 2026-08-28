import asyncio
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.collectors.gdelt import GdeltCollector
from app.collectors.rss import RssCollector, RssFeed
from app.services.news_collector import NewsCollectionService
from app.database.session import create_tables, get_session
from app.services.article_storage import ArticleStorageService
from app.services.article_analysis import ArticleAnalysisService, build_analyzer
from datetime import datetime
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database.models import Article, ArticleAnalysis, PostDraft
from app.database.session import SessionLocal
from app.services.draft_generation import DraftGenerationService, build_draft_writer
from app.services.telegram_publication import build_publication_service
from app.services.languages import language_menu, supported_languages
from app.services.scheduling import SchedulingService
from app.scheduler.publications import ScheduledPublicationWorker
from app.services.owner_controls import OwnerControlService, control_panel
from app.telegram.publisher import TelegramPublisher

settings = get_settings()

news_service = NewsCollectionService(
    collectors=[
        GdeltCollector(),
        RssCollector(
            feeds=[
                RssFeed("OpenAI News", "https://openai.com/news/rss.xml"),
                RssFeed(
                    "TechCrunch AI",
                    "https://techcrunch.com/category/artificial-intelligence/feed/",
                ),
            ]
        ),
    ]
)
article_storage_service = ArticleStorageService()
article_analysis_service = ArticleAnalysisService(
    build_analyzer(settings), settings.analysis_minimum_score
)
draft_generation_service = DraftGenerationService(
    build_draft_writer(settings), settings.content_max_hashtags
)
scheduling_service = SchedulingService()


async def run_scheduled_publications() -> None:
    """Worker entry point; publishing is inactive unless explicitly enabled."""
    if not settings.auto_publish_scheduled:
        return
    session = SessionLocal()
    try:
        service = build_publication_service(settings.telegram_bot_token, settings.telegram_channel_id)
        await ScheduledPublicationWorker(service).publish_due(session)
    finally:
        session.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    scheduler = AsyncIOScheduler(timezone=settings.scheduler_timezone)
    if settings.scheduler_enabled:
        scheduler.add_job(run_scheduled_publications, "interval", minutes=1, id="scheduled-publications")
        scheduler.start()
    try:
        yield
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Confirm that the web application is running."""
    return {"status": "ok", "environment": settings.app_env}


@app.get("/news/collect", tags=["news"])
async def collect_news(
    query: str | None = Query(default=None, min_length=2),
    limit: int = Query(default=settings.news_collection_limit, ge=1, le=100),
) -> list[dict[str, object]]:
    """Collect and normalize current news without storing it yet."""
    articles = await news_service.collect(query or settings.news_query, limit)
    return [article.model_dump(mode="json") for article in articles]


@app.get("/database/health", tags=["system"])
def database_health(session: Session = Depends(get_session)) -> dict[str, str]:
    """Confirm that the configured PostgreSQL database accepts queries."""
    session.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.post("/news/collect-and-store", tags=["news"])
async def collect_and_store_news(
    query: str | None = Query(default=None, min_length=2),
    limit: int = Query(default=settings.news_collection_limit, ge=1, le=100),
    session: Session = Depends(get_session),
) -> dict[str, int]:
    """Collect articles, store only unseen records, and report the outcome."""
    articles = await news_service.collect(query or settings.news_query, limit)
    summary = article_storage_service.store(articles, session)
    return {"collected": len(articles), "stored": summary.stored, "duplicates": summary.duplicates}


@app.post("/database/setup", tags=["system"])
def setup_database() -> dict[str, str]:
    """Create the initial schema in a new local development database."""
    create_tables()
    return {"status": "ok"}


@app.post("/articles/{article_id}/analyze", tags=["analysis"])
async def analyze_article(article_id: UUID, session: Session = Depends(get_session)) -> dict[str, object]:
    """Score one stored article and persist its editorial decision."""
    article = session.get(Article, article_id)
    if article is None:
        return {"status": "not_found"}
    record = await article_analysis_service.analyze_and_store(article, session)
    response: dict[str, object] = {
        "status": "ok",
        "article_id": str(article.id),
        "relevance": record.relevance,
        "importance": record.importance,
        "novelty": record.novelty,
        "viral_potential": record.viral_potential,
        "credibility": record.credibility,
        "final_score": record.final_score,
        "category": record.category,
        "recommended": record.recommended,
        "breaking": record.breaking,
        "reasoning": record.reasoning,
        "provider": record.provider,
    }
    if record.breaking and settings.auto_publish_breaking:
        draft = await draft_generation_service.generate_and_store(article, session)
        publication_service = build_publication_service(
            settings.telegram_bot_token, settings.telegram_channel_id
        )
        publication = await publication_service.approve_and_publish(draft, session)
        response["breaking_publication"] = {
            "status": "published",
            "telegram_message_id": publication.telegram_message_id,
        }
    return response


@app.get("/articles", tags=["news"])
def list_articles(
    limit: int = Query(default=20, ge=1, le=100), session: Session = Depends(get_session)
) -> list[dict[str, object]]:
    """List recent stored articles so an article can be selected for analysis."""
    articles = session.scalars(
        select(Article).order_by(Article.collected_at.desc()).limit(limit)
    ).all()
    return [
        {
            "id": str(article.id),
            "title": article.title,
            "source_name": article.source_name,
            "url": article.url,
            "collected_at": article.collected_at,
        }
        for article in articles
    ]


@app.get("/articles/ready-for-draft", tags=["news"])
def list_articles_ready_for_draft(
    limit: int = Query(default=20, ge=1, le=100), session: Session = Depends(get_session)
) -> list[dict[str, object]]:
    """List recommended articles that have not already produced a draft."""
    articles = session.scalars(
        select(Article)
        .join(ArticleAnalysis, ArticleAnalysis.article_id == Article.id)
        .outerjoin(PostDraft, PostDraft.article_id == Article.id)
        .where(ArticleAnalysis.recommended.is_(True), PostDraft.id.is_(None))
        .order_by(ArticleAnalysis.final_score.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": str(article.id),
            "title": article.title,
            "source_name": article.source_name,
            "url": article.url,
        }
        for article in articles
    ]


@app.post("/articles/{article_id}/draft", tags=["drafts"])
async def generate_draft(article_id: UUID, session: Session = Depends(get_session)) -> dict[str, object]:
    """Generate and save a Telegram-ready draft for a recommended article."""
    article = session.get(Article, article_id)
    if article is None:
        return {"status": "not_found"}
    draft = await draft_generation_service.generate_and_store(article, session)
    return {
        "status": draft.status,
        "draft_id": str(draft.id),
        "article_id": str(draft.article_id),
        "headline": draft.headline,
        "post_text": draft.post_text,
        "hashtags": draft.hashtags,
        "provider": draft.provider,
    }


@app.get("/drafts", tags=["drafts"])
def list_drafts(
    limit: int = Query(default=20, ge=1, le=100), session: Session = Depends(get_session)
) -> list[dict[str, object]]:
    """List reviewable drafts; nothing is sent to Telegram in this phase."""
    drafts = session.scalars(select(PostDraft).order_by(PostDraft.updated_at.desc()).limit(limit)).all()
    return [
        {
            "id": str(draft.id),
            "article_id": str(draft.article_id),
            "headline": draft.headline,
            "post_text": draft.post_text,
            "status": draft.status,
            "provider": draft.provider,
        }
        for draft in drafts
    ]


@app.get("/telegram/status", tags=["telegram"])
def telegram_status() -> dict[str, bool]:
    """Report configuration availability without exposing Telegram credentials."""
    return {"configured": bool(settings.telegram_bot_token and settings.telegram_channel_id)}


@app.post("/drafts/{draft_id}/approve-and-publish", tags=["telegram"])
async def approve_and_publish_draft(
    draft_id: UUID, session: Session = Depends(get_session)
) -> dict[str, object]:
    """Explicitly approve one draft and publish it once to the configured channel."""
    draft = session.get(PostDraft, draft_id)
    if draft is None:
        return {"status": "not_found"}
    service = build_publication_service(settings.telegram_bot_token, settings.telegram_channel_id)
    publication = await service.approve_and_publish(draft, session)
    return {
        "status": "published",
        "draft_id": str(draft.id),
        "telegram_message_id": publication.telegram_message_id,
    }


@app.get("/languages", tags=["languages"])
def list_languages() -> list[dict[str, object]]:
    """List supported reader languages and whether their public channel is configured."""
    return [
        {
            "code": language.code,
            "label": language.label,
            "native_label": language.native_label,
            "available": language.destination_url is not None or language.code == "en",
        }
        for language in supported_languages(settings)
    ]


@app.get("/languages/menu", tags=["languages"])
def get_language_menu() -> dict[str, object]:
    """Return a Telegram inline-keyboard-compatible language chooser."""
    return language_menu(settings)


def build_owner_controls() -> OwnerControlService:
    if not settings.telegram_bot_token or not settings.telegram_channel_id or not settings.telegram_owner_chat_id:
        raise HTTPException(status_code=503, detail="Owner bot controls are not configured")
    bot = TelegramPublisher(settings.telegram_bot_token)
    return OwnerControlService(
        news_service,
        article_storage_service,
        article_analysis_service,
        draft_generation_service,
        scheduling_service,
        build_publication_service(settings.telegram_bot_token, settings.telegram_channel_id),
        bot,
        settings.telegram_owner_chat_id,
    )


@app.post("/telegram/webhook", tags=["telegram"])
async def telegram_webhook(
    update: dict[str, object],
    secret: str | None = Header(default=None, alias="X-Telegram-Bot-Api-Secret-Token"),
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    """Receive owner-only Telegram commands and inline-button callbacks."""
    if not settings.telegram_webhook_secret or secret != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")
    controls = build_owner_controls()
    callback = update.get("callback_query")
    if isinstance(callback, dict):
        sender = callback.get("from")
        data = callback.get("data")
        callback_id = callback.get("id")
        if not isinstance(sender, dict) or str(sender.get("id")) != settings.telegram_owner_chat_id:
            raise HTTPException(status_code=403, detail="Only the owner can use this bot")
        if data == "find" and isinstance(callback_id, str):
            await controls.bot.answer_callback(callback_id, "Searching the latest news…")
            await controls.bot.send_message(settings.telegram_owner_chat_id, "🔎 Searching the latest news…")

            async def search_in_background() -> None:
                background_session = SessionLocal()
                try:
                    sent = await controls.find_news(
                        background_session,
                        "artificial intelligence OR OpenAI OR ChatGPT OR AI",
                        settings.owner_find_limit,
                        settings.owner_find_timeout_seconds,
                    )
                    await controls.bot.send_message(
                        settings.telegram_owner_chat_id,
                        f"Search complete: {sent} draft(s) ready for review.",
                    )
                except Exception:
                    await controls.bot.send_message(
                        settings.telegram_owner_chat_id,
                        "Search could not finish. Please try Find news again.",
                    )
                finally:
                    background_session.close()

            asyncio.create_task(search_in_background())
        elif isinstance(data, str) and isinstance(callback_id, str):
            result = await controls.handle_callback(data, session)
            await controls.bot.answer_callback(callback_id, result)
        return {"ok": True}
    message = update.get("message")
    if isinstance(message, dict):
        chat = message.get("chat")
        text = message.get("text")
        if isinstance(chat, dict) and str(chat.get("id")) == settings.telegram_owner_chat_id:
            if text in {"/start", "/menu", "/find"}:
                await controls.bot.send_message(settings.telegram_owner_chat_id, "Adabary owner controls", control_panel())
    return {"ok": True}


@app.post("/telegram/webhook/setup", tags=["telegram"])
async def setup_telegram_webhook() -> dict[str, str]:
    """Register the deployed HTTPS webhook after PUBLIC_BASE_URL is configured."""
    if not settings.telegram_bot_token or not settings.telegram_webhook_secret or not settings.public_base_url:
        raise HTTPException(status_code=503, detail="Webhook configuration is incomplete")
    await TelegramPublisher(settings.telegram_bot_token).set_webhook(
        f"{settings.public_base_url.rstrip('/')}/telegram/webhook", settings.telegram_webhook_secret
    )
    return {"status": "ok"}


@app.get("/breaking", tags=["scheduler"])
def list_breaking_news(
    limit: int = Query(default=20, ge=1, le=100), session: Session = Depends(get_session)
) -> list[dict[str, object]]:
    """Show breaking candidates before auto-breaking delivery is enabled."""
    analyses = session.scalars(
        select(ArticleAnalysis)
        .where(ArticleAnalysis.breaking.is_(True))
        .order_by(ArticleAnalysis.analyzed_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "article_id": str(analysis.article_id),
            "final_score": analysis.final_score,
            "category": analysis.category,
            "reasoning": analysis.reasoning,
        }
        for analysis in analyses
    ]


@app.post("/drafts/{draft_id}/schedule", tags=["scheduler"])
def schedule_draft(
    draft_id: UUID,
    scheduled_for: datetime,
    session: Session = Depends(get_session),
) -> dict[str, object]:
    """Schedule a draft for future delivery; scheduler automation is config-controlled."""
    draft = session.get(PostDraft, draft_id)
    if draft is None:
        return {"status": "not_found"}
    record = scheduling_service.schedule(draft, scheduled_for, session)
    return {"status": record.status, "schedule_id": str(record.id), "scheduled_for": record.scheduled_for}
