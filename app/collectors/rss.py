import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import feedparser
import httpx

from app.collectors.models import NewsArticle, is_usable_article


@dataclass(frozen=True)
class RssFeed:
    name: str
    url: str


class RssCollector:
    """Collect articles from curated RSS and official announcement feeds."""

    name = "RSS"
    # A single publisher must never hold up every other source.  This stays
    # below the owner-search budget, so successful feeds can still be used.
    per_feed_timeout_seconds = 4.0

    def __init__(self, feeds: list[RssFeed]) -> None:
        self.feeds = feeds

    async def collect(
        self, query: str, limit: int, client: httpx.AsyncClient | None = None
    ) -> list[NewsArticle]:
        del query  # Curated feeds already define their editorial scope.
        owns_client = client is None
        client = client or httpx.AsyncClient(timeout=20.0, follow_redirects=True)
        try:
            async def fetch_feed(feed: RssFeed) -> list[NewsArticle]:
                try:
                    response = await asyncio.wait_for(
                        client.get(feed.url), timeout=self.per_feed_timeout_seconds
                    )
                    response.raise_for_status()
                except (asyncio.TimeoutError, httpx.HTTPError):
                    return []
                parsed = feedparser.parse(response.content)
                feed_articles: list[NewsArticle] = []
                for entry in parsed.entries:
                    article = self._normalize(entry, feed)
                    if article and is_usable_article(article):
                        feed_articles.append(article)
                        if len(feed_articles) >= limit:
                            break
                return feed_articles

            # return_exceptions keeps one malformed publisher response from
            # discarding articles already received from the other publishers.
            results = await asyncio.gather(
                *(fetch_feed(feed) for feed in self.feeds), return_exceptions=True
            )
            articles = [
                article
                for feed_articles in results
                if isinstance(feed_articles, list)
                for article in feed_articles
            ]
            return articles[:limit]
        finally:
            if owns_client:
                await client.aclose()

    def _normalize(self, entry: object, feed: RssFeed) -> NewsArticle | None:
        title = getattr(entry, "title", None)
        link = getattr(entry, "link", None)
        if not isinstance(title, str) or not isinstance(link, str):
            return None
        published_at = self._parse_date(getattr(entry, "published", None))
        summary = getattr(entry, "summary", None)
        try:
            return NewsArticle(
                title=title.strip(),
                url=link,
                source_name=feed.name,
                source_url=feed.url,
                published_at=published_at,
                summary=summary if isinstance(summary, str) else None,
            )
        except ValueError:
            return None

    @staticmethod
    def _parse_date(value: object) -> datetime | None:
        if not isinstance(value, str):
            return None
        try:
            parsed = parsedate_to_datetime(value)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except (TypeError, ValueError):
            return None
