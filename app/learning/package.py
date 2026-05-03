from app.config import get_settings
from app.models import Article, NotebookPackage
from app.profile import PERSONA_SUMMARY


def build_notebook_package(primary_article: Article, related_sources: list[Article], language: str = "en") -> NotebookPackage:
    sources = [primary_article, *related_sources]
    guide = _build_guide(primary_article, related_sources)
    return NotebookPackage(
        title=f"Learning Pack: {primary_article.title[:80]}",
        primary_article=primary_article,
        sources=sources,
        guide_markdown=guide,
        language=language,
    )


def _build_guide(primary_article: Article, related_sources: list[Article]) -> str:
    settings = get_settings()
    source_lines = "\n".join(f"- {source.title} ({source.source}): {source.url}" for source in related_sources)
    return f"""# Learning Guide

## Primary Article

{primary_article.title}

{primary_article.summary}

## What to Learn

- The core event or development behind the article.
- The strategic, technical, market, and policy concepts that explain why it matters.
- Why this matters to a Singapore-based technology leader working on China-Singapore AI collaboration.
- The implications for AI deployment, governance, public-sector transformation, and regional technology cooperation.

## Learner Context

{PERSONA_SUMMARY}

## Output Requirements

- Podcast / Audio Overview: target length around {settings.podcast_target_minutes} minutes, in English, conversational but executive-level.
- Infographic: concise, clear, easy to understand, with no more than 6 key blocks.
- Avoid generic AI commentary. Give sharp, grounded analysis based on the supplied sources.

## Suggested NotebookLM Prompts

1. Explain the key concepts behind this article for a senior technology and policy audience.
2. Create a concise briefing with the facts, implications, risks, and open questions.
3. Generate an Audio Overview in English, around {settings.podcast_target_minutes} minutes, with a sharp focus on AI deployment, governance, and cross-border collaboration.
4. Create a concise infographic outline with 5-6 blocks, clear labels, and simple explanations.
5. Suggest three LinkedIn-ready viewpoints that connect this topic to China-Singapore technology cooperation.

## Additional Sources

{source_lines}
"""
