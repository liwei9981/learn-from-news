from datetime import datetime, timezone

from app.models import Article, SourceType
from app.search.ranking import canonical_domain, score_articles


def test_canonical_domain_strips_www():
    assert canonical_domain("https://www.reuters.com/world/example") == "reuters.com"


def test_score_articles_prioritizes_relevance_and_authority():
    articles = [
        Article(
            title="Lifestyle roundup",
            url="https://example.com/lifestyle",
            source="Example",
            summary="A general article.",
            source_type=SourceType.HIGH_TRAFFIC,
        ),
        Article(
            title="AI chips reshape semiconductor supply chains",
            url="https://www.reuters.com/technology/ai-chips",
            source="Reuters",
            published_at=datetime.now(timezone.utc),
            summary="AI chips and semiconductor export controls are changing the market.",
            source_type=SourceType.HOT_NEWS,
        ),
    ]
    scored = score_articles(articles, "AI chips")
    assert "Reuters" == scored[0].article.source

