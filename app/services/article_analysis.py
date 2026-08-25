from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.heuristic import HeuristicAnalyzer
from app.ai.models import AnalysisResult
from app.ai.openai_responses import OpenAIResponsesAnalyzer
from app.collectors.models import NewsArticle
from app.config import Settings
from app.database.models import Article, ArticleAnalysis


class ArticleAnalyzer(Protocol):
    async def analyze(self, article: NewsArticle) -> AnalysisResult: ...


def build_analyzer(settings: Settings) -> ArticleAnalyzer:
    if settings.analysis_provider.casefold() == "openai":
        if not settings.ai_api_key or not settings.ai_model:
            raise ValueError("OpenAI analysis requires AI_API_KEY and AI_MODEL in .env")
        return OpenAIResponsesAnalyzer(settings.ai_api_key, settings.ai_base_url, settings.ai_model)
    return HeuristicAnalyzer()


class ArticleAnalysisService:
    def __init__(self, analyzer: ArticleAnalyzer, minimum_score: int) -> None:
        self.analyzer = analyzer
        self.minimum_score = minimum_score

    async def analyze_and_store(self, article: Article, session: Session) -> ArticleAnalysis:
        analysis = await self.analyzer.analyze(
            NewsArticle(
                title=article.title,
                url=article.url,
                source_name=article.source_name,
                source_url=article.source_url,
                summary=article.summary,
                image_url=article.image_url,
                published_at=article.published_at,
            )
        )
        record = session.scalar(select(ArticleAnalysis).where(ArticleAnalysis.article_id == article.id))
        values = analysis.model_dump()
        values["recommended"] = analysis.final_score >= self.minimum_score
        if record is None:
            record = ArticleAnalysis(article_id=article.id, **values)
            session.add(record)
        else:
            for field, value in values.items():
                setattr(record, field, value)
        session.commit()
        session.refresh(record)
        return record
