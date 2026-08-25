import pytest

from app.collectors.models import NewsArticle
from app.services.news_collector import NewsCollectionService


class WorkingCollector:
    name = "working"

    async def collect(self, query: str, limit: int) -> list[NewsArticle]:
        return [
            NewsArticle(
                title="A real technology story from a test collector",
                url="https://example.com/story",
                source_name="Test",
            )
        ]


class FailingCollector:
    name = "failing"

    async def collect(self, query: str, limit: int) -> list[NewsArticle]:
        raise RuntimeError("provider unavailable")


@pytest.mark.asyncio
async def test_service_continues_when_a_provider_fails() -> None:
    articles = await NewsCollectionService([WorkingCollector(), FailingCollector()]).collect(
        "AI", 10
    )

    assert [article.source_name for article in articles] == ["Test"]
