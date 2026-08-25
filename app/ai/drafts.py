from pydantic import BaseModel, Field


class DraftResult(BaseModel):
    """Structured content ready for later review and Telegram publishing."""

    headline: str = Field(min_length=1, max_length=300)
    post_text: str = Field(min_length=1, max_length=4096)
    hashtags: list[str] = Field(default_factory=list, max_length=5)
    provider: str
