from html import unescape
from re import sub

from bs4 import BeautifulSoup

PERSONA_SUMMARY = (
    "China-born, based in Singapore for 26 years, deeply localized, strong technology background, "
    "former long-term experience in Singapore's government technology sector, now focused on "
    "China-Singapore technology collaboration, especially AI."
)

HIGH_INTEREST_TERMS = {
    "ai": 1.0,
    "artificial intelligence": 1.0,
    "agentic": 0.9,
    "chips": 0.85,
    "semiconductor": 0.85,
    "compute": 0.75,
    "cloud": 0.65,
    "data center": 0.7,
    "governance": 0.9,
    "regulation": 0.8,
    "public sector": 0.9,
    "government": 0.7,
    "digital government": 1.0,
    "singapore": 1.0,
    "china": 1.0,
    "asean": 0.85,
    "southeast asia": 0.85,
    "cross-border": 0.85,
    "collaboration": 0.75,
    "partnership": 0.7,
    "innovation": 0.65,
    "deployment": 0.8,
    "enterprise ai": 0.75,
    "startup": 0.55,
}


def persona_interest_score(text: str) -> float:
    lowered = text.lower()
    score = 0.0
    for term, weight in HIGH_INTEREST_TERMS.items():
        if term in lowered:
            score += weight
    return min(1.0, score / 3.0)


def clean_article_summary(summary: str) -> str:
    if not summary:
        return ""
    decoded = unescape(summary)
    text = BeautifulSoup(decoded, "html.parser").get_text(" ", strip=True)
    text = unescape(text)
    text = sub(r"\s+", " ", text).strip()
    return text


def summarize_article_for_telegram(title: str, summary: str) -> str:
    base = clean_article_summary(summary) or clean_article_summary(title) or title.strip()
    base = " ".join(base.split())
    if len(base) > 500:
        base = f"{base[:497].rstrip()}..."

    sentences = _split_sentences(base)
    if len(sentences) >= 4:
        return " ".join(sentences[:5])

    title_clean = clean_article_summary(title) or title.strip()
    paragraph = [
        f"This article covers {title_clean}.",
        base if base and base != title_clean else "It points to a development that is worth watching beyond the headline.",
        "The key issue is not only what happened, but what it signals for technology strategy, market structure, and policy choices.",
        "For an AI and technology reader in Singapore, the useful question is how this may affect deployment, governance, and regional collaboration.",
        "The original article is worth reading for the specific facts and source context.",
    ]
    return " ".join(paragraph)


def _split_sentences(text: str) -> list[str]:
    parts = sub(r"(?<=[.!?])\s+", "\n", text).splitlines()
    return [part.strip() for part in parts if part.strip()]
