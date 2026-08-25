from pydantic import BaseModel, Field


class AnalysisResult(BaseModel):
    """Structured editorial decision returned by every analysis provider."""

    relevance: int = Field(ge=0, le=100)
    importance: int = Field(ge=0, le=100)
    novelty: int = Field(ge=0, le=100)
    viral_potential: int = Field(ge=0, le=100)
    credibility: int = Field(ge=0, le=100)
    final_score: int = Field(ge=0, le=100)
    category: str = Field(min_length=1, max_length=100)
    recommended: bool
    breaking: bool
    reasoning: str = Field(min_length=1, max_length=1000)
    provider: str
