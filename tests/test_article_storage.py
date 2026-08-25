from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.collectors.models import NewsArticle
from app.database.articles import ArticleRepository, article_hash, canonicalize_url
from app.database.models import Base
from app.services.article_storage import ArticleStorageService


def make_session():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def article(url: str, title: str = "OpenAI releases important new model") -> NewsArticle:
    return NewsArticle(title=title, url=url, source_name="Example News")


def test_canonicalize_url_removes_tracking_parameters() -> None:
    assert canonicalize_url("https://example.com/story/?utm_source=rss&ref=home#section") == (
        "https://example.com/story?ref=home"
    )


def test_repository_returns_existing_article_for_canonical_url() -> None:
    session = make_session()
    repository = ArticleRepository(session)

    first = repository.save_if_new(article("https://example.com/story?utm_source=rss"))
    duplicate = repository.save_if_new(article("https://example.com/story"))

    assert first.created is True
    assert duplicate.created is False
    assert duplicate.article.id == first.article.id


def test_repository_detects_same_headline_from_another_source() -> None:
    session = make_session()
    repository = ArticleRepository(session)

    first = repository.save_if_new(article("https://first.example/story"))
    duplicate = repository.save_if_new(article("https://second.example/story"))

    assert first.created is True
    assert duplicate.created is False
    assert article_hash(first.article.title) == duplicate.article.content_hash


def test_storage_summary_counts_new_and_duplicate_articles() -> None:
    session = make_session()
    summary = ArticleStorageService().store(
        [
            article("https://example.com/first"),
            article("https://example.com/first?utm_source=rss"),
        ],
        session,
    )

    assert summary.stored == 1
    assert summary.duplicates == 1
