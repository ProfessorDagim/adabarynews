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

    def __init__(self, feeds: list[RssFeed]) -> None:
        self.feeds = feeds

    async def collect(
        self, query: str, limit: int, client: httpx.AsyncClient | None = None
    ) -> list[NewsArticle]:
        del query  # Curated feeds already define their editorial scope.
        owns_client = client is None
        client = client or httpx.AsyncClient(timeout=20.0, follow_redirects=True)
        try:
            articles: list[NewsArticle] = []
            for feed in self.feeds:
                try:
                    response = await client.get(feed.url)
                    response.raise_for_status()
                except httpx.HTTPError:
                    continue
                parsed = feedparser.parse(response.content)
                for entry in parsed.entries:
                    article = self._normalize(entry, feed)
                    if article and is_usable_article(article):
                        articles.append(article)
                        if len(articles) >= limit:
                            return articles
            return articles
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
