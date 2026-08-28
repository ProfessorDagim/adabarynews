from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env."""

    app_name: str = "Adabary News Engine"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    news_query: str = (
        "artificial intelligence OR OpenAI OR ChatGPT OR Anthropic OR Gemini OR "
        "NVIDIA OR robotics"
    )
    news_collection_limit: int = 20
    owner_find_limit: int = 5
    owner_find_timeout_seconds: float = 6.0
    analysis_provider: str = "heuristic"
    analysis_minimum_score: int = 70
    ai_api_key: str | None = None
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str | None = None
    content_provider: str = "heuristic"
    content_max_hashtags: int = 3
    telegram_bot_token: str | None = None
    telegram_channel_id: str | None = None
    telegram_amharic_channel_url: str | None = None
    telegram_oromo_channel_url: str | None = None
    telegram_tigrinya_channel_url: str | None = None
    scheduler_enabled: bool = False
    auto_publish_scheduled: bool = False
    auto_publish_breaking: bool = False
    scheduler_timezone: str = "Africa/Nairobi"
    telegram_owner_chat_id: str | None = None
    telegram_webhook_secret: str | None = None
    public_base_url: str | None = None
    database_url: str = (
        "postgresql+psycopg://adabary:adabary_dev_only@localhost:5432/adabary_news"
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
