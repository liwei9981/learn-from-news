from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

from app.models import Article, ScoredArticle, SourceType
from app.profile import persona_interest_score


SOURCE_AUTHORITY = {
    "reuters.com": 1.0,
    "apnews.com": 1.0,
    "bbc.com": 0.92,
    "ft.com": 0.9,
    "economist.com": 0.9,
    "bloomberg.com": 0.88,
    "cnn.com": 0.82,
    "techcrunch.com": 0.82,
    "technologyreview.com": 0.85,
    "wired.com": 0.78,
    "theverge.com": 0.76,
    "brookings.edu": 0.86,
    "rand.org": 0.86,
    "oecd.org": 0.86,
    "imf.org": 0.86,
    "arxiv.org": 0.8,
    "semianalysis.com": 0.82,
    "substack.com": 0.55,
    "medium.com": 0.48,
}


def canonical_domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def dedupe_articles(articles: list[Article]) -> list[Article]:
    seen: set[str] = set()
    unique: list[Article] = []
    for article in articles:
        key = str(article.url).rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        unique.append(article)
    return unique


def score_articles(articles: list[Article], query: str) -> list[ScoredArticle]:
    unique = dedupe_articles(articles)
    query_terms = {term.lower() for term in query.split() if len(term) > 2}
    now = datetime.now(timezone.utc)
    scored = []

    for article in unique:
        domain = canonical_domain(str(article.url))
        text = f"{article.title} {article.summary}".lower()
        relevance = _term_overlap(text, query_terms)
        freshness = _freshness(article.published_at, now)
        authority = SOURCE_AUTHORITY.get(domain, 0.5)
        depth = _depth_score(article)
        traffic = _traffic_proxy(article)
        persona = persona_interest_score(text)

        score = (
            relevance * 0.20
            + persona * 0.18
            + freshness * 0.18
            + authority * 0.18
            + _source_type_score(article.source_type) * 0.12
            + depth * 0.10
            + traffic * 0.04
        )
        reasons = [
            f"relevance={relevance:.2f}",
            f"persona={persona:.2f}",
            f"freshness={freshness:.2f}",
            f"authority={authority:.2f}",
            f"depth={depth:.2f}",
        ]
        scored.append(ScoredArticle(article=article, score=round(score, 4), reasons=reasons))

    return sorted(scored, key=lambda item: item.score, reverse=True)


def split_bundle(scored: list[ScoredArticle], max_results: int) -> tuple[list[ScoredArticle], list[ScoredArticle]]:
    top_news = [item for item in scored if item.article.source_type != SourceType.DEEP_CONTEXT]
    deep_context = [item for item in scored if item.article.source_type == SourceType.DEEP_CONTEXT]
    return top_news[:max_results], deep_context[:max_results]


def _term_overlap(text: str, query_terms: set[str]) -> float:
    if not query_terms:
        return 0.0
    hits = sum(1 for term in query_terms if term in text)
    return min(1.0, hits / max(1, len(query_terms)))


def _freshness(published_at: datetime | None, now: datetime) -> float:
    if published_at is None:
        return 0.45
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    age_hours = max(0.0, (now - published_at).total_seconds() / 3600)
    if age_hours <= 24:
        return 1.0
    if age_hours <= 72:
        return 0.8
    if age_hours <= 24 * 7:
        return 0.6
    if age_hours <= 24 * 30:
        return 0.35
    return 0.15


def _depth_score(article: Article) -> float:
    text_len = len(article.summary)
    if article.source_type == SourceType.DEEP_CONTEXT:
        return 0.85
    if text_len > 800:
        return 0.8
    if text_len > 250:
        return 0.55
    return 0.35


def _traffic_proxy(article: Article) -> float:
    if article.source_type == SourceType.HIGH_TRAFFIC:
        return 0.9
    if article.source_type == SourceType.HOT_NEWS:
        return 0.75
    if article.source_type == SourceType.MAINSTREAM:
        return 0.65
    return 0.45


def _source_type_score(source_type: SourceType) -> float:
    return {
        SourceType.HOT_NEWS: 0.9,
        SourceType.MAINSTREAM: 0.8,
        SourceType.HIGH_TRAFFIC: 0.72,
        SourceType.DEEP_CONTEXT: 0.65,
    }[source_type]
