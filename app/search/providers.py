from __future__ import annotations

import asyncio
import logging
import ssl
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Protocol
from urllib.parse import quote_plus

import aiohttp
import certifi
import feedparser
from googlenewsdecoder import gnewsdecoder

from app.config import Settings
from app.models import Article, SearchRequest, SourceType
from app.profile import clean_article_summary

logger = logging.getLogger(__name__)


class SearchProvider(Protocol):
    async def search(self, request: SearchRequest) -> list[Article]:
        ...


class GoogleNewsRssProvider:
    async def search(self, request: SearchRequest) -> list[Article]:
        query = quote_plus(f"{request.query} when:{request.lookback_days}d")
        url = (
            "https://news.google.com/rss/search?"
            f"q={query}&hl={request.language.upper()}&gl={request.region}&ceid={request.region}:en"
        )
        async with _client_session() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                body = await response.text()
        feed = feedparser.parse(body)
        articles = []
        for entry in feed.entries[: request.max_results]:
            published_at = _parse_feed_date(getattr(entry, "published", None))
            article_url = await _decode_google_news_url(entry.link)
            articles.append(
                Article(
                    title=entry.title,
                    url=article_url,
                    source=getattr(entry, "source", {}).get("title", "Google News"),
                    published_at=published_at,
                    summary=clean_article_summary(getattr(entry, "summary", "")),
                    source_type=SourceType.HOT_NEWS,
                    language=request.language,
                )
            )
        return articles


class NewsApiProvider:
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def search(self, request: SearchRequest) -> list[Article]:
        params = {
            "q": request.query,
            "language": request.language,
            "sortBy": "publishedAt",
            "pageSize": str(request.max_results),
            "apiKey": self.api_key,
            "from": _since_date(request.lookback_days),
        }
        async with _client_session() as session:
            async with session.get("https://newsapi.org/v2/everything", params=params) as response:
                response.raise_for_status()
                payload = await response.json()
        articles = []
        for item in payload.get("articles", [])[: request.max_results]:
            if not item.get("url") or not item.get("title"):
                continue
            articles.append(
                Article(
                    title=item["title"],
                    url=item["url"],
                    source=(item.get("source") or {}).get("name") or "NewsAPI",
                    published_at=_parse_iso_datetime(item.get("publishedAt")),
                    summary=clean_article_summary(item.get("description") or ""),
                    source_type=SourceType.HOT_NEWS,
                    language=request.language,
                )
            )
        return articles


class GdeltProvider:
    async def search(self, request: SearchRequest) -> list[Article]:
        params = {
            "query": request.query,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": str(request.max_results),
            "sort": "HybridRel",
            "startdatetime": _gdelt_since(request.lookback_days),
        }
        async with _client_session() as session:
            async with session.get("https://api.gdeltproject.org/api/v2/doc/doc", params=params) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        articles = []
        for item in payload.get("articles", [])[: request.max_results]:
            if not item.get("url") or not item.get("title"):
                continue
            articles.append(
                Article(
                    title=item["title"],
                    url=item["url"],
                    source=item.get("sourceCountry") or item.get("domain") or "GDELT",
                    published_at=_parse_gdelt_datetime(item.get("seendate")),
                    summary=clean_article_summary(item.get("snippet") or ""),
                    source_type=SourceType.HOT_NEWS,
                    language=request.language,
                    metadata={"domain": item.get("domain"), "source_country": item.get("sourceCountry")},
                )
            )
        return articles


class GoogleProgrammableSearchProvider:
    def __init__(self, api_key: str, cse_id: str):
        self.api_key = api_key
        self.cse_id = cse_id

    async def search(self, request: SearchRequest) -> list[Article]:
        params = {
            "key": self.api_key,
            "cx": self.cse_id,
            "q": request.query,
            "num": str(min(request.max_results, 10)),
            "lr": f"lang_{request.language}",
            "dateRestrict": f"d{request.lookback_days}",
        }
        async with _client_session() as session:
            async with session.get("https://www.googleapis.com/customsearch/v1", params=params) as response:
                response.raise_for_status()
                payload = await response.json()
        articles = []
        for item in payload.get("items", [])[: request.max_results]:
            if not item.get("link") or not item.get("title"):
                continue
            articles.append(
                Article(
                    title=item["title"],
                    url=item["link"],
                    source=item.get("displayLink") or "Google Search",
                    summary=clean_article_summary(item.get("snippet") or ""),
                    source_type=SourceType.HIGH_TRAFFIC,
                    language=request.language,
                    metadata={"cache_id": item.get("cacheId")},
                )
            )
        return articles


class TavilyProvider:
    def __init__(self, api_key: str, include_domains: list[str] | None = None):
        self.api_key = api_key
        self.include_domains = include_domains or []

    async def search(self, request: SearchRequest) -> list[Article]:
        body = {
            "query": request.query,
            "topic": "news",
            "search_depth": "advanced",
            "max_results": request.max_results,
            "days": request.lookback_days,
            "include_raw_content": False,
            "include_domains": self.include_domains,
        }
        async with _client_session() as session:
            async with session.post(
                "https://api.tavily.com/search",
                json=body,
                headers={"Authorization": f"Bearer {self.api_key}"},
            ) as response:
                response.raise_for_status()
                payload = await response.json()
        return [
            Article(
                title=item["title"],
                url=item["url"],
                source=item.get("url", "").split("/")[2] if item.get("url") else "Tavily",
                summary=clean_article_summary(item.get("content") or ""),
                published_at=None,
                source_type=SourceType.DEEP_CONTEXT,
                language=request.language,
                metadata={"tavily_score": item.get("score")},
            )
            for item in payload.get("results", [])
            if item.get("title") and item.get("url")
        ]


class FallbackProvider:
    async def search(self, request: SearchRequest) -> list[Article]:
        now = datetime.now(timezone.utc)
        topic = request.query
        return [
            Article(
                title=f"{topic}: latest developments and market implications",
                url="https://example.com/latest-developments",
                source="Fallback News",
                published_at=now,
                summary=f"A placeholder hot news item for {topic}. Add API keys to enable live search.",
                source_type=SourceType.HOT_NEWS,
                language=request.language,
            ),
            Article(
                title=f"{topic}: deep background and policy context",
                url="https://example.com/deep-context",
                source="Fallback Context",
                published_at=now,
                summary=f"A placeholder deep-context article for {topic}.",
                source_type=SourceType.DEEP_CONTEXT,
                language=request.language,
            ),
        ]


def build_providers(settings: Settings) -> list[SearchProvider]:
    providers: list[SearchProvider] = [GoogleNewsRssProvider(), GdeltProvider()]
    if settings.news_api_key:
        providers.append(NewsApiProvider(settings.news_api_key))
    if settings.google_cse_api_key and settings.google_cse_id:
        providers.append(GoogleProgrammableSearchProvider(settings.google_cse_api_key, settings.google_cse_id))
    if settings.tavily_api_key:
        providers.append(TavilyProvider(settings.tavily_api_key))
    if not providers:
        providers.append(FallbackProvider())
    return providers


def _client_session() -> aiohttp.ClientSession:
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    timeout = aiohttp.ClientTimeout(total=8)
    return aiohttp.ClientSession(connector=connector, timeout=timeout)


async def run_providers(providers: list[SearchProvider], request: SearchRequest) -> list[Article]:
    results = await asyncio.gather(
        *(provider.search(request) for provider in providers),
        return_exceptions=True,
    )
    articles: list[Article] = []
    for result in results:
        if isinstance(result, Exception):
            logger.warning("Search provider failed: %s: %s", type(result).__name__, result)
            continue
        articles.extend(result)
    if not articles and __import__("app.config").config.get_settings().allow_fallback_results:
        articles = await FallbackProvider().search(request)
    return articles


def _parse_feed_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _parse_gdelt_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.strptime(value[:14], "%Y%m%d%H%M%S")
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc)


def _since_date(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()


def _gdelt_since(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y%m%d%H%M%S")


async def _decode_google_news_url(url: str) -> str:
    if "news.google.com" not in url:
        return url
    try:
        result = await asyncio.to_thread(gnewsdecoder, url)
    except Exception as exc:
        logger.warning("Google News URL decode failed: %s", exc)
        return url
    if isinstance(result, dict) and result.get("status") and result.get("decoded_url"):
        return str(result["decoded_url"])
    logger.warning("Google News URL decode returned no decoded URL: %s", result)
    return url
