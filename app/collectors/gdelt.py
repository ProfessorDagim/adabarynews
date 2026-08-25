from datetime import datetime

import httpx

from app.collectors.models import NewsArticle, is_usable_article


class GdeltCollector:
    """Collect recent article links from GDELT's public DOC API."""

    name = "GDELT"
    endpoint = "https://api.gdeltproject.org/api/v2/doc/doc"

    async def collect(
        self, query: str, limit: int, client: httpx.AsyncClient | None = None
    ) -> list[NewsArticle]:
        owns_client = client is None
        client = client or httpx.AsyncClient(timeout=20.0)
        try:
            response = await client.get(
                self.endpoint,
                params={
                    "query": query,
                    "mode": "artlist",
                    "format": "json",
                    "maxrecords": min(limit, 250),
                    "sort": "datedesc",
                },
            )
            response.raise_for_status()
            records = response.json().get("articles", [])
            articles: list[NewsArticle] = []
            for record in records:
                article = self._normalize(record)
                if article and is_usable_article(article):
                    articles.append(article)
            return articles[:limit]
        finally:
            if owns_client:
                await client.aclose()

    def _normalize(self, record: dict[str, object]) -> NewsArticle | None:
        title = record.get("title")
        url = record.get("url")
        if not isinstance(title, str) or not isinstance(url, str):
            return None

        seen_date = record.get("seendate")
        published_at = None
        if isinstance(seen_date, str):
            try:
                published_at = datetime.strptime(seen_date, "%Y%m%dT%H%M%SZ")
            except ValueError:
                pass

        try:
            return NewsArticle(
                title=title.strip(),
                url=url,
                source_name=str(record.get("domain") or self.name),
                source_url=url,
                published_at=published_at,
                image_url=record.get("socialimage") or None,
            )
        except (TypeError, ValueError):
            return None
