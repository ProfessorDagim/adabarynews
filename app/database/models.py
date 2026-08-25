import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all persistent database records."""


class Article(Base):
    """A collected article retained for de-duplication and later editorial work."""

    __tablename__ = "articles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(String(2048), unique=True)
    canonical_url: Mapped[str] = mapped_column(String(2048), unique=True, index=True)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    source_name: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ArticleAnalysis(Base):
    """Editorial scoring for an article, produced by a configured analyzer."""

    __tablename__ = "article_analyses"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    article_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("articles.id", ondelete="CASCADE"), unique=True, index=True
    )
    relevance: Mapped[int] = mapped_column(Integer)
    importance: Mapped[int] = mapped_column(Integer)
    novelty: Mapped[int] = mapped_column(Integer)
    viral_potential: Mapped[int] = mapped_column(Integer)
    credibility: Mapped[int] = mapped_column(Integer)
    final_score: Mapped[int] = mapped_column(Integer, index=True)
    category: Mapped[str] = mapped_column(String(100))
    recommended: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    breaking: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    reasoning: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(100))
    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PostDraft(Base):
    """A reviewable Telegram post draft. Publishing is deliberately a later phase."""

    __tablename__ = "post_drafts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    article_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("articles.id", ondelete="CASCADE"), unique=True, index=True
    )
    headline: Mapped[str] = mapped_column(String(300))
    post_text: Mapped[str] = mapped_column(Text)
    hashtags: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    provider: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TelegramPublication(Base):
    """An immutable record of a successful Telegram publishing action."""

    __tablename__ = "telegram_publications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    draft_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("post_drafts.id", ondelete="CASCADE"), unique=True, index=True
    )
    channel_id: Mapped[str] = mapped_column(String(200))
    telegram_message_id: Mapped[int] = mapped_column(Integer)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ScheduledPublication(Base):
    """A planned publishing action, kept separate from drafts for auditability."""

    __tablename__ = "scheduled_publications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    draft_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("post_drafts.id", ondelete="CASCADE"), unique=True, index=True
    )
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(30), default="scheduled", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
