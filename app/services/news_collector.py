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

    async def collect(
        self, query: str, limit: int, timeout_seconds: float | None = None
    ) -> list[NewsArticle]:
        """Collect from all providers, optionally returning after a short deadline."""
        tasks = [
            asyncio.create_task(collector.collect(query, limit)) for collector in self.collectors
        ]
        if timeout_seconds is None:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            _, pending = await asyncio.wait(tasks, timeout=timeout_seconds)
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            results: list[list[NewsArticle] | Exception] = []
            for task in tasks:
                if not task.done() or task.cancelled():
                    continue
                try:
                    results.append(task.result())
                except Exception as exc:
                    results.append(exc)
        source_articles = [result for result in results if not isinstance(result, Exception)]
        unique: dict[str, NewsArticle] = {}
        # Rotate between providers so a large result set from one source cannot
        # crowd out official feeds that contain a newer, undrafted story.
        while any(source_articles):
            for articles in source_articles:
                if articles:
                    article = articles.pop(0)
                    unique.setdefault(str(article.url), article)
                    if len(unique) >= limit:
                        return list(unique.values())
        return list(unique.values())[:limit]
