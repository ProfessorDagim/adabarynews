from app.ai.models import AnalysisResult
from app.collectors.models import NewsArticle


class HeuristicAnalyzer:
    """A transparent local baseline used until an LLM provider is configured."""

    provider_name = "heuristic"
    topic_words = {
        "ai", "artificial intelligence", "openai", "chatgpt", "anthropic", "claude",
        "gemini", "google ai", "nvidia", "robotics", "machine learning", "automation",
    }
    launch_words = {"launch", "launches", "released", "releases", "announced", "unveils", "introducing"}
    urgent_words = {"breaking", "outage", "ban", "acquisition", "funding", "partnership"}

    async def analyze(self, article: NewsArticle) -> AnalysisResult:
        text = f"{article.title} {article.summary or ''}".casefold()
        matches = sum(word in text for word in self.topic_words)
        source = article.source_name.casefold()
        source_url = (article.source_url or "").casefold()
        official = any(name in source or name in source_url for name in ("openai", "anthropic", "google", "nvidia", "microsoft", "meta"))
        credible_publication = any(name in source for name in ("reuters", "associated press", "techcrunch", "the verge", "wired"))

        credibility = 95 if official else 82 if credible_publication else 60
        relevance = min(100, 30 + matches * 22 + (25 if official else 0))
        importance = min(
            100,
            35 + matches * 15 + (15 if official else 0)
            + (20 if any(word in text for word in self.launch_words) else 0),
        )
        novelty = 72 if any(word in text for word in self.launch_words) else 62 if official else 50
        viral = min(
            100,
            30 + matches * 12 + (10 if official else 0)
            + (20 if any(word in text for word in self.urgent_words) else 0),
        )
        final_score = round(relevance * 0.30 + importance * 0.25 + novelty * 0.15 + viral * 0.15 + credibility * 0.15)
        category = "Robotics" if "robot" in text else "AI" if matches else "Technology"
        breaking = official and any(word in text for word in self.launch_words | self.urgent_words) and final_score >= 80
        recommended = final_score >= 70
        reasoning = (
            f"Matched {matches} channel-topic signals; source credibility is "
            f"{'official' if official else 'publication' if credible_publication else 'unverified'}"
        )
        return AnalysisResult(
            relevance=relevance,
            importance=importance,
            novelty=novelty,
            viral_potential=viral,
            credibility=credibility,
            final_score=final_score,
            category=category,
            recommended=recommended,
            breaking=breaking,
            reasoning=reasoning,
            provider=self.provider_name,
        )
