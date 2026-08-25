import pytest
from fastapi import HTTPException

from app.ai.heuristic_writer import HeuristicDraftWriter
from app.database.models import Article, ArticleAnalysis
from app.services.draft_generation import DraftGenerationService
from tests.test_article_storage import make_session


def make_article_and_analysis(session, recommended: bool = True):
    article = Article(
        title="OpenAI releases a new model for developers",
        url="https://openai.com/news/model",
        canonical_url="https://openai.com/news/model",
        content_hash="b" * 64,
        source_name="OpenAI News",
        summary="OpenAI released a new model for developers.",
    )
    session.add(article)
    session.commit()
    analysis = ArticleAnalysis(
        article_id=article.id,
        relevance=95,
        importance=90,
        novelty=85,
        viral_potential=88,
        credibility=95,
        final_score=91,
        category="AI",
        recommended=recommended,
        breaking=False,
        reasoning="Official AI release with strong relevance.",
        provider="heuristic",
    )
    session.add(analysis)
    session.commit()
    return article


@pytest.mark.asyncio
async def test_draft_is_generated_for_a_recommended_article() -> None:
    session = make_session()
    article = make_article_and_analysis(session)

    draft = await DraftGenerationService(HeuristicDraftWriter(), 3).generate_and_store(article, session)

    assert draft.status == "draft"
    assert "Source: OpenAI News" in draft.post_text
    assert draft.hashtags == "#AI #ArtificialIntelligence #Tech"


@pytest.mark.asyncio
async def test_draft_is_rejected_for_non_recommended_article() -> None:
    session = make_session()
    article = make_article_and_analysis(session, recommended=False)

    with pytest.raises(HTTPException, match="Only recommended"):
        await DraftGenerationService(HeuristicDraftWriter(), 3).generate_and_store(article, session)


@pytest.mark.asyncio
async def test_published_article_cannot_be_drafted_again() -> None:
    session = make_session()
    article = make_article_and_analysis(session)
    service = DraftGenerationService(HeuristicDraftWriter(), 3)
    draft = await service.generate_and_store(article, session)
    draft.status = "published"
    session.commit()

    with pytest.raises(HTTPException, match="cannot be drafted again"):
        await service.generate_and_store(article, session)
