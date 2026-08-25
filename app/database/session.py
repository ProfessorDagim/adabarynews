from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.database.models import Base


def build_engine(database_url: str) -> Engine:
    """Create a database engine without opening a connection eagerly.

    Neon supplies standard ``postgresql://`` URLs.  This project uses the
    modern psycopg driver, so make that driver explicit before SQLAlchemy
    constructs the engine.
    """
    # Some browser dashboards wrap long connection strings with non-breaking
    # spaces.  PostgreSQL host names cannot contain whitespace, so discard it
    # before handing the URL to SQLAlchemy.
    database_url = "".join(database_url.split())
    if database_url.startswith("postgres://"):
        database_url = "postgresql+psycopg://" + database_url.removeprefix("postgres://")
    elif database_url.startswith("postgresql://"):
        database_url = "postgresql+psycopg://" + database_url.removeprefix("postgresql://")
    return create_engine(database_url, pool_pre_ping=True)


engine = build_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def create_tables() -> None:
    """Create Phase 3 tables; migrations will replace this in a later phase."""
    Base.metadata.create_all(bind=engine)
