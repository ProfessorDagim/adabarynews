from app.database.session import build_engine


def test_standard_postgres_url_uses_psycopg_driver() -> None:
    engine = build_engine("postgresql://user:password@example.com:5432/adabary")

    assert engine.url.drivername == "postgresql+psycopg"


def test_existing_psycopg_url_is_unchanged() -> None:
    engine = build_engine("postgresql+psycopg://user:password@example.com:5432/adabary")

    assert engine.url.drivername == "postgresql+psycopg"
