from datetime import datetime

from pydantic import BaseModel, HttpUrl


class NewsArticle(BaseModel):
    """A provider-neutral news article used by the collection pipeline."""

    title: str
    url: HttpUrl
    source_name: str
    source_url: str | None = None
    published_at: datetime | None = None
    summary: str | None = None
    image_url: HttpUrl | None = None


def is_usable_article(article: NewsArticle) -> bool:
    """Reject incomplete records before they enter later pipeline stages."""
    return len(article.title.strip()) >= 12 and article.url.scheme in {"http", "https"}
