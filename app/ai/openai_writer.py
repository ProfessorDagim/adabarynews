import json

import httpx

from app.ai.drafts import DraftResult
from app.database.models import Article, ArticleAnalysis


class OpenAIDraftWriter:
    """Optional Responses API writer that returns a schema-validated Telegram draft."""

    provider_name = "openai"

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.endpoint = f"{base_url.rstrip('/')}/responses"
        self.model = model

    async def generate(self, article: Article, analysis: ArticleAnalysis) -> DraftResult:
        article_data = {
            "title": article.title,
            "summary": article.summary,
            "source_name": article.source_name,
            "url": article.url,
            "category": analysis.category,
            "reasoning": analysis.reasoning,
        }
        payload = {
            "model": self.model,
            "store": False,
            "instructions": (
                "Write a concise Telegram news post from only the supplied facts. "
                "Use a strong but non-sensational hook, short paragraphs, a clear why-it-matters "
                "line, source attribution, and up to three relevant hashtags. Do not invent facts."
            ),
            "input": json.dumps(article_data),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "telegram_draft",
                    "strict": True,
                    "schema": DraftResult.model_json_schema(),
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
        output_text = response.json().get("output_text")
        if not isinstance(output_text, str):
            raise ValueError("OpenAI response did not include structured output text")
        return DraftResult.model_validate_json(output_text).model_copy(
            update={"provider": self.provider_name}
        )
