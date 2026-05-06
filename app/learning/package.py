from app.config import get_settings
from app.models import Article, NotebookPackage
from app.profile import PERSONA_SUMMARY


def build_notebook_package(
    primary_article: Article,
    related_sources: list[Article],
    learning_points: list[str] | None = None,
    language: str = "en",
) -> NotebookPackage:
    lp = learning_points or []
    sources = [primary_article, *related_sources]
    guide = _build_guide(primary_article, related_sources, lp)
    return NotebookPackage(
        title=f"Learning Pack: {primary_article.title[:80]}",
        primary_article=primary_article,
        sources=sources,
        guide_markdown=guide,
        language=language,
        learning_points=lp,
    )


def _build_guide(
    primary_article: Article,
    related_sources: list[Article],
    learning_points: list[str],
) -> str:
    settings = get_settings()
    source_lines = "\n".join(
        f"- {s.title} ({s.source}): {s.url}" for s in related_sources
    )
    lp_lines = (
        "\n".join(f"{i + 1}. {lp}" for i, lp in enumerate(learning_points))
        if learning_points
        else "(no specific learning points selected)"
    )
    lp_objectives = ""
    if learning_points:
        objectives = "\n".join(
            f"- **{lp}**: explain what it is, provide background and historical context, "
            f"and connect it clearly to the news article."
            for lp in learning_points
        )
        lp_objectives = f"\n\nFor each selected learning point:\n{objectives}"

    return f"""# Learning Guide

## Primary News Article

**{primary_article.title}**

{primary_article.summary}

Source: {primary_article.url}

## Selected Learning Points

The learner has chosen these specific points to study in depth:

{lp_lines}

## Learning Objectives
{lp_objectives}

## Learner Context

{PERSONA_SUMMARY}

## Output Requirements

- **Podcast / Audio Overview**: target {settings.podcast_target_minutes} minutes, English, conversational, executive-level.
  - Start with a 2-minute news brief (what happened, why it matters)
  - Then deep dive into each selected learning point with background and context
  - Close with how the learning points connect to the bigger picture
- **Infographic**: portrait-oriented, CONCISE detail level, max 6 blocks:
  - Section 1 — News Brief: (a) What Happened, (b) Why It Matters
  - Section 2 — Learning Points: one block per selected point with a clear heading,
    2-sentence explanation, and 1-sentence connection to the news

## Additional Sources

{source_lines}
"""
