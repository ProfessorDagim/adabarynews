import httpx
import pytest

from app.collectors.gdelt import GdeltCollector
from app.collectors.rss import RssCollector, RssFeed


@pytest.mark.asyncio
async def test_gdelt_collector_normalizes_valid_records() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "articles": [
                    {
                        "title": "OpenAI releases a new research update",
                        "url": "https://example.com/openai-update",
                        "domain": "example.com",
                        "seendate": "20260822T080000Z",
                    },
                    {"title": "short", "url": "https://example.com/skip"},
                ]
            },
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        articles = await GdeltCollector().collect("OpenAI", 10, client)

    assert len(articles) == 1
    assert articles[0].source_name == "example.com"
    assert str(articles[0].url) == "https://example.com/openai-update"


@pytest.mark.asyncio
async def test_rss_collector_normalizes_feed_entries() -> None:
    xml = b"""<?xml version='1.0'?><rss version='2.0'><channel><title>Test</title>
    <item><title>Important artificial intelligence announcement</title>
    <link>https://example.com/article</link><pubDate>Fri, 22 Aug 2026 08:00:00 GMT</pubDate>
    <description>Summary text</description></item></channel></rss>"""
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=xml))
    async with httpx.AsyncClient(transport=transport) as client:
        articles = await RssCollector([RssFeed("Test Feed", "https://feed.test/rss")]).collect(
            "unused", 10, client
        )

    assert len(articles) == 1
    assert articles[0].source_name == "Test Feed"
    assert articles[0].published_at is not None


@pytest.mark.asyncio
async def test_rss_collector_continues_after_one_feed_fails() -> None:
    xml = b"""<?xml version='1.0'?><rss version='2.0'><channel><title>Test</title>
    <item><title>Important artificial intelligence announcement</title>
    <link>https://example.com/article</link></item></channel></rss>"""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "unavailable.test":
            return httpx.Response(503)
        return httpx.Response(200, content=xml)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        articles = await RssCollector(
            [
                RssFeed("Unavailable", "https://unavailable.test/rss"),
                RssFeed("Available", "https://available.test/rss"),
            ]
        ).collect("unused", 10, client)

    assert [article.source_name for article in articles] == ["Available"]
