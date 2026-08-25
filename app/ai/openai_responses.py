import json

import httpx

from app.ai.models import AnalysisResult
from app.collectors.models import NewsArticle


class OpenAIResponsesAnalyzer:
    """Optional OpenAI Responses API analyzer using schema-constrained JSON output."""

    provider_name = "openai"

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.endpoint = f"{base_url.rstrip('/')}/responses"
        self.model = model

    async def analyze(self, article: NewsArticle) -> AnalysisResult:
        payload = {
            "model": self.model,
            "store": False,
            "instructions": (
                "You are an exacting editor for an AI and technology Telegram channel. "
                "Score only the supplied article; do not invent facts."
            ),
            "input": json.dumps(article.model_dump(mode="json")),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "news_analysis",
                    "strict": True,
                    "schema": AnalysisResult.model_json_schema(),
                }
            },
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            response.raise_for_status()
        data = response.json()
        output_text = data.get("output_text")
        if not isinstance(output_text, str):
            raise ValueError("OpenAI response did not include structured output text")
        return AnalysisResult.model_validate_json(output_text).model_copy(
            update={"provider": self.provider_name}
        )
