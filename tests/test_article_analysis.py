import pytest

from app.ai.heuristic import HeuristicAnalyzer
from app.collectors.models import NewsArticle
from app.database.models import Article
from app.services.article_analysis import ArticleAnalysisService
from tests.test_article_storage import make_session


@pytest.mark.asyncio
async def test_relevant_official_ai_news_is_recommended() -> None:
    result = await HeuristicAnalyzer().analyze(
        NewsArticle(
            title="OpenAI announces and releases a new AI model for ChatGPT",
            url="https://openai.com/news/model",
            source_name="OpenAI News",
            source_url="https://openai.com/news/rss.xml",
        )
    )

    assert result.category == "AI"
    assert result.recommended is True
    assert result.credibility == 95
    assert result.final_score >= 70


@pytest.mark.asyncio
async def test_unrelated_news_is_not_recommended() -> None:
    result = await HeuristicAnalyzer().analyze(
        NewsArticle(
            title="Local community holds its annual summer festival",
            url="https://example.com/festival",
            source_name="Example Local News",
        )
    )

    assert result.category == "Technology"
    assert result.recommended is False


@pytest.mark.asyncio
async def test_analysis_is_saved_and_updated_for_an_article() -> None:
    session = make_session()
    article = Article(
        title="NVIDIA announces new AI platform",
        url="https://nvidia.com/news/platform",
        canonical_url="https://nvidia.com/news/platform",
        content_hash="a" * 64,
        source_name="NVIDIA News",
    )
    session.add(article)
    session.commit()

    service = ArticleAnalysisService(HeuristicAnalyzer(), minimum_score=70)
    first = await service.analyze_and_store(article, session)
    second = await service.analyze_and_store(article, session)

    assert first.article_id == article.id
    assert second.id == first.id
