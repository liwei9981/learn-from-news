from __future__ import annotations

import logging
import re

from app.models import Article

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a learning coach. Your job is to read a news article and identify the key concepts, "
    "ideas, or historical events mentioned in the news that a reader could learn something valuable from. "
    "These are NOT summaries of the article — they are specific things referenced in or behind the news "
    "that are worth studying to understand the story more deeply."
)

_USER_PROMPT_TMPL = """\
Read this news article carefully. Identify exactly 5 things mentioned in or behind the news \
that are worth learning about. These should be:

- A specific concept or technical idea (e.g. "Retrieval-Augmented Generation (RAG)")
- A historical event or policy that shaped the context (e.g. "The 1985 Plaza Accord")
- An important person or organisation and their role (e.g. "Jensen Huang's GPU computing vision")
- A trend or emerging pattern worth understanding (e.g. "Sovereign AI infrastructure movement")
- A specific data point or fact that reveals something deeper (e.g. "China's 40% share of global AI patents")

Each learning point should be a short, specific phrase (5–12 words) — \
something a curious reader would want to look up and study further.

Do NOT list generic themes like "AI implications" or "geopolitical tensions". \
Be specific to what this particular article mentions or references.

Article title: {title}
Summary: {summary}

Return exactly 5 learning points, one per line, numbered 1–5. No extra text.\
"""


async def extract_learning_points(
    article: Article,
    api_key: str | None,
    model: str = "gemini-2.5-pro-preview-05-06",
) -> list[str]:
    """Extract 5 learning points from an article using Gemini. Falls back to rule-based."""
    if api_key:
        try:
            return await _gemini_extract(article, api_key, model)
        except Exception as exc:
            logger.warning("Gemini LP extraction failed, using fallback: %s: %s", type(exc).__name__, exc)
    return _rule_based_extract(article)


async def _gemini_extract(article: Article, api_key: str, model: str) -> list[str]:
    from google import genai  # type: ignore[import]

    client = genai.Client(api_key=api_key)
    prompt = _USER_PROMPT_TMPL.format(
        title=article.title,
        summary=(article.summary or "")[:1500],
    )
    response = await client.aio.models.generate_content(
        model=model,
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
        ),
    )
    raw = response.text or ""
    points = _parse_numbered_list(raw)
    if len(points) >= 3:
        logger.info("Gemini extracted %d learning points", len(points))
        return points[:5]
    logger.warning("Gemini returned too few learning points (%d), using fallback", len(points))
    return _rule_based_extract(article)


def _parse_numbered_list(text: str) -> list[str]:
    points: list[str] = []
    for line in text.strip().splitlines():
        line = line.strip()
        match = re.match(r"^\d+[\.\)]\s*(.+)$", line)
        if match:
            points.append(match.group(1).strip())
        elif line and not re.match(r"^\d+$", line) and len(line) > 5:
            # Accept bare lines too in case model skips numbering
            if len(points) < 5:
                points.append(line)
    return points


def _rule_based_extract(article: Article) -> list[str]:
    """Lightweight fallback: pull capitalised noun phrases from title + summary."""
    text = f"{article.title}. {article.summary or ''}"
    # Find sequences of capitalised words (named entities / proper nouns)
    candidates = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b", text)
    seen: set[str] = set()
    unique: list[str] = []
    for c in candidates:
        if c.lower() not in seen and len(c) > 4:
            seen.add(c.lower())
            unique.append(c)

    # Supplement with generic frames if needed
    generic = [
        "Key concepts and implications",
        "Historical context and background",
        "Technology and policy impact",
        "Important stakeholders involved",
        "Relevance to AI and cross-border collaboration",
    ]
    combined = unique[:5] + generic
    return combined[:5]
