import asyncio

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


class SlowCollector:
    name = "slow"

    async def collect(self, query: str, limit: int) -> list[NewsArticle]:
        await asyncio.sleep(1)
        return []


class MultiStoryCollector:
    name = "many"

    async def collect(self, query: str, limit: int) -> list[NewsArticle]:
        return [
            NewsArticle(
                title=f"Technology story number {number}",
                url=f"https://example.com/story-{number}",
                source_name="Many",
            )
            for number in range(limit)
        ]


@pytest.mark.asyncio
async def test_service_continues_when_a_provider_fails() -> None:
    articles = await NewsCollectionService([WorkingCollector(), FailingCollector()]).collect(
        "AI", 10
    )

    assert [article.source_name for article in articles] == ["Test"]


@pytest.mark.asyncio
async def test_service_rotates_between_sources() -> None:
    articles = await NewsCollectionService([MultiStoryCollector(), WorkingCollector()]).collect(
        "AI", 3
    )

    assert [article.source_name for article in articles] == ["Many", "Test", "Many"]


@pytest.mark.asyncio
async def test_service_returns_completed_sources_after_timeout() -> None:
    articles = await NewsCollectionService([WorkingCollector(), SlowCollector()]).collect(
        "AI", 10, timeout_seconds=0.01
    )

    assert [article.source_name for article in articles] == ["Test"]
