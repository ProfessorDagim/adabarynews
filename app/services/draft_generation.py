from typing import Protocol

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.drafts import DraftResult
from app.ai.heuristic_writer import HeuristicDraftWriter
from app.ai.openai_writer import OpenAIDraftWriter
from app.config import Settings
from app.database.models import Article, ArticleAnalysis, PostDraft


class DraftWriter(Protocol):
    async def generate(self, article: Article, analysis: ArticleAnalysis) -> DraftResult: ...


def build_draft_writer(settings: Settings) -> DraftWriter:
    if settings.content_provider.casefold() == "openai":
        if not settings.ai_api_key or not settings.ai_model:
            raise ValueError("OpenAI drafting requires AI_API_KEY and AI_MODEL in .env")
        return OpenAIDraftWriter(settings.ai_api_key, settings.ai_base_url, settings.ai_model)
    return HeuristicDraftWriter()


class DraftGenerationService:
    def __init__(self, writer: DraftWriter, max_hashtags: int) -> None:
        self.writer = writer
        self.max_hashtags = max_hashtags

    async def generate_and_store(self, article: Article, session: Session) -> PostDraft:
        analysis = session.scalar(
            select(ArticleAnalysis).where(ArticleAnalysis.article_id == article.id)
        )
        if analysis is None:
            raise HTTPException(status_code=409, detail="Analyze the article before generating a draft")
        if not analysis.recommended:
            raise HTTPException(status_code=422, detail="Only recommended articles can become drafts")

        draft = await self.writer.generate(article, analysis)
        record = session.scalar(select(PostDraft).where(PostDraft.article_id == article.id))
        values = draft.model_dump()
        values["hashtags"] = " ".join(draft.hashtags[: self.max_hashtags])
        if record is None:
            record = PostDraft(article_id=article.id, status="draft", **values)
            session.add(record)
        else:
            if record.status == "published":
                raise HTTPException(status_code=409, detail="A published article cannot be drafted again")
            for field, value in values.items():
                setattr(record, field, value)
            record.status = "draft"
        session.commit()
        session.refresh(record)
        return record
