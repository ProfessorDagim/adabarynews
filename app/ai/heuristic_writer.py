from app.ai.drafts import DraftResult
from app.database.models import Article, ArticleAnalysis


class HeuristicDraftWriter:
    """Creates a fact-preserving local draft when no LLM provider is configured."""

    provider_name = "heuristic"

    async def generate(self, article: Article, analysis: ArticleAnalysis) -> DraftResult:
        icon = "🚨" if analysis.breaking else "🧠"
        headline = f"{icon} {article.title}"[:300]
        summary = article.summary or "A new development has been reported."
        hashtags = self._hashtags(analysis.category)
        post_text = (
            f"{headline}\n\n{summary.strip()}\n\n"
            f"💡 Why it matters: {analysis.reasoning}\n\n"
            f"Source: {article.source_name}\n{article.url}\n\n"
            f"{' '.join(hashtags)}"
        )[:4096]
        return DraftResult(
            headline=headline,
            post_text=post_text,
            hashtags=hashtags,
            provider=self.provider_name,
        )

    @staticmethod
    def _hashtags(category: str) -> list[str]:
        mapping = {
            "AI": ["#AI", "#ArtificialIntelligence", "#Tech"],
            "Robotics": ["#Robotics", "#AI", "#Technology"],
        }
        return mapping.get(category, ["#Technology", "#News"])
