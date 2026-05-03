from app.models import Article, LinkedInPost
from app.profile import clean_article_summary


USER_PERSONA = (
    "The author is China-born, has lived in Singapore for 26 years, "
    "has deep technology experience, previously worked for Singapore's government technology sector, "
    "and now advances China-Singapore technology collaboration, especially in AI."
)


def generate_linkedin_post(
    article: Article,
    angle: str = "balanced",
    infographic_available: bool = False,
) -> LinkedInPost:
    text = _template_post(article, angle, infographic_available)
    share_url = "https://www.linkedin.com/feed/"
    return LinkedInPost(text=text, article_url=article.url, share_url=share_url)


def _template_post(article: Article, angle: str, infographic_available: bool) -> str:
    summary = _article_summary(article)
    if angle == "policy":
        opinion = (
            "My view: the real policy signal is that AI advantage is moving from model performance "
            "to trusted execution. The winners will be the institutions that can align governance, "
            "infrastructure, and deployment speed."
        )
    elif angle == "technical":
        opinion = (
            "My view: the technical signal is not only what the technology can do, but how fast it "
            "can be integrated into real workflows. In AI, execution discipline is becoming as "
            "important as invention."
        )
    else:
        opinion = (
            "My view: this is another sign that AI is becoming core innovation infrastructure, "
            "not just a headline topic. The real question is how quickly it can become trusted, "
            "deployable capability across markets and borders."
        )

    infographic_line = (
        "I also attached a concise NotebookLM infographic from a quick search around the main topic."
        if infographic_available
        else "I would also recommend making a quick infographic summary around the main topic before sharing it internally."
    )
    return (
        f"{summary}\n\n"
        f"{opinion}\n\n"
        f"Read the article here: {article.url}\n"
        f"{infographic_line}"
    )


def _article_summary(article: Article) -> str:
    title = clean_article_summary(article.title)
    summary = clean_article_summary(article.summary or "")
    if not summary:
        return f"This article reports on {title}."

    first_sentence = summary.split(". ")[0].strip()
    if first_sentence and not first_sentence.endswith("."):
        first_sentence += "."
    if len(first_sentence) > 260:
        first_sentence = first_sentence[:257].rstrip() + "..."
    return f"This article reports on {title}. {first_sentence}"
