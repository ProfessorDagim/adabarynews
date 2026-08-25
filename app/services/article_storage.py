from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.collectors.models import NewsArticle
from app.database.articles import ArticleRepository


@dataclass(frozen=True)
class StorageSummary:
    stored: int
    duplicates: int


class ArticleStorageService:
    """Store a collection run and count newly discovered versus known articles."""

    def store(self, articles: list[NewsArticle], session: Session) -> StorageSummary:
        repository = ArticleRepository(session)
        stored = 0
        duplicates = 0
        for article in articles:
            result = repository.save_if_new(article)
            if result.created:
                stored += 1
            else:
                duplicates += 1
        return StorageSummary(stored=stored, duplicates=duplicates)
