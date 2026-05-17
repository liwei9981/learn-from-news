from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class SourceType(StrEnum):
    HOT_NEWS = "hot_news"
    MAINSTREAM = "mainstream"
    DEEP_CONTEXT = "deep_context"
    HIGH_TRAFFIC = "high_traffic"


class Article(BaseModel):
    title: str
    url: HttpUrl
    source: str
    published_at: datetime | None = None
    summary: str = ""
    source_type: SourceType = SourceType.HOT_NEWS
    language: str = "en"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScoredArticle(BaseModel):
    article: Article
    score: float
    reasons: list[str] = Field(default_factory=list)


class SearchRequest(BaseModel):
    query: str
    language: str = "en"
    region: str = "US"
    max_results: int = 10
    lookback_days: int = 7


class SearchBundle(BaseModel):
    query: str
    top_news: list[ScoredArticle]
    deep_context: list[ScoredArticle]


class NotebookPackage(BaseModel):
    title: str
    primary_article: Article
    sources: list[Article]
    guide_markdown: str
    language: str = "en"
    learning_points: list[str] = Field(default_factory=list)


class NotebookResult(BaseModel):
    notebook_id: str | None = None
    notebook_url: str | None = None
    infographic_url: str | None = None
    infographic_path: str | None = None
    status: str = "prepared"
    notes: str = ""


class LinkedInPost(BaseModel):
    text: str
    article_url: HttpUrl
    share_url: str


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
