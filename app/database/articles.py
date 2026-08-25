import hashlib
import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.collectors.models import NewsArticle
from app.database.models import Article

TRACKING_PARAMETERS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


@dataclass(frozen=True)
class SaveArticleResult:
    article: Article
    created: bool


def canonicalize_url(url: str) -> str:
    """Remove common marketing parameters so one link has one stable identity."""
    parts = urlsplit(url)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.casefold() not in TRACKING_PARAMETERS and not key.casefold().startswith("utm_")
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), urlencode(query), ""))


def article_hash(title: str) -> str:
    """Create a stable title fingerprint for cross-source duplicate headlines."""
    normalized = re.sub(r"\s+", " ", title).strip().casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class ArticleRepository:
    """Persist articles and return an existing record when a duplicate is collected."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save_if_new(self, incoming: NewsArticle) -> SaveArticleResult:
        url = str(incoming.url)
        canonical_url = canonicalize_url(url)
        content_hash = article_hash(incoming.title)
        existing = self.session.scalar(
            select(Article).where(
                or_(
                    Article.canonical_url == canonical_url,
                    Article.content_hash == content_hash,
                )
            )
        )
        if existing:
            return SaveArticleResult(article=existing, created=False)

        article = Article(
            title=incoming.title,
            url=url,
            canonical_url=canonical_url,
            content_hash=content_hash,
            source_name=incoming.source_name,
            source_url=incoming.source_url,
            summary=incoming.summary,
            image_url=str(incoming.image_url) if incoming.image_url else None,
            published_at=incoming.published_at,
        )
        self.session.add(article)
        self.session.commit()
        self.session.refresh(article)
        return SaveArticleResult(article=article, created=True)
