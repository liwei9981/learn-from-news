from __future__ import annotations

import logging

from app.models import Article

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a professional who shares concise, insightful LinkedIn posts about technology "
    "and policy news. Write in a natural, curious, first-person tone. Keep it short and human."
)

_USER_PROMPT_TMPL = """\
Write a LinkedIn post about this news article.

Requirements:
- 2 to 3 sentences only — short, concise, and friendly
- Naturally share the news and bring up the selected learning points below
- Write with genuine curiosity and a good learning attitude
- End by inviting people to read the article (woven in naturally, not a separate line)
- No hashtags
- Do NOT include the article URL (it will be added separately)
- First person, natural human tone

News title: {title}
Summary: {summary}

Learning points to highlight:
{learning_points_text}\
"""


async def generate_linkedin_post(
    article: Article,
    learning_points: list[str],
    api_key: str | None,
    model: str = "gemini-2.5-pro-preview-05-06",
) -> str:
    """Generate a clean LinkedIn post ready to copy-paste. Returns post text + URL."""
    post_body = ""
    if api_key:
        try:
            post_body = await _gemini_post(article, learning_points, api_key, model)
        except Exception as exc:
            logger.warning("Gemini LinkedIn post failed, using fallback: %s: %s", type(exc).__name__, exc)

    if not post_body:
        post_body = _fallback_post(article, learning_points)

    return f"{post_body}\n\n{article.url}"


async def _gemini_post(
    article: Article,
    learning_points: list[str],
    api_key: str,
    model: str,
) -> str:
    from google import genai  # type: ignore[import]

    client = genai.Client(api_key=api_key)
    lp_text = "\n".join(f"- {lp}" for lp in learning_points) if learning_points else "- General interest in the news"
    prompt = _USER_PROMPT_TMPL.format(
        title=article.title,
        summary=(article.summary or "")[:800],
        learning_points_text=lp_text,
    )
    response = await client.aio.models.generate_content(
        model=model,
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
        ),
    )
    text = (response.text or "").strip()
    # Remove any accidental URL the model might include
    lines = [ln for ln in text.splitlines() if "http" not in ln.lower()]
    return " ".join(" ".join(lines).split())


def _fallback_post(article: Article, learning_points: list[str]) -> str:
    """Simple string-assembly fallback when Gemini is unavailable."""
    title = article.title.rstrip(".")
    if learning_points:
        lp_phrase = " and ".join(f'"{lp}"' for lp in learning_points[:2])
        return (
            f"Came across this piece on {title}. "
            f"What caught my attention was the discussion around {lp_phrase} — "
            f"worth a read if you're following how these ideas are shaping the field."
        )
    return (
        f"Interesting read on {title}. "
        f"The implications for technology and policy are worth exploring — "
        f"check it out if you're curious about where this is heading."
    )
