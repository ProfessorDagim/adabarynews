import asyncio
from typing import Protocol

from app.collectors.models import NewsArticle


class NewsProvider(Protocol):
    name: str

    async def collect(self, query: str, limit: int) -> list[NewsArticle]: ...


class NewsCollectionService:
    """Collect from independent providers; one failed provider does not stop a run."""

    def __init__(self, collectors: list[NewsProvider]) -> None:
        self.collectors = collectors

    async def collect(self, query: str, limit: int) -> list[NewsArticle]:
        results = await asyncio.gather(
            *(collector.collect(query, limit) for collector in self.collectors),
            return_exceptions=True,
        )
        articles: list[NewsArticle] = []
        for result in results:
            if not isinstance(result, Exception):
                articles.extend(result)
        return articles[:limit]
