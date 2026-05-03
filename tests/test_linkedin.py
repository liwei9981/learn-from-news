from app.linkedin import generate_linkedin_post
from app.models import Article


def test_linkedin_post_contains_share_url_and_article_url():
    article = Article(
        title="AI policy shifts in Asia",
        url="https://example.com/ai-policy",
        source="Example",
        summary="A test article.",
    )
    post = generate_linkedin_post(article)
    assert "linkedin.com/feed" in post.share_url
    assert "https://example.com/ai-policy" in post.text


def test_linkedin_post_does_not_explicitly_name_personal_background():
    article = Article(
        title="AI policy shifts in Asia",
        url="https://example.com/ai-policy",
        source="Example",
        summary="A test article.",
    )
    post = generate_linkedin_post(article)
    lowered = post.text.lower()
    assert "having worked" not in lowered
    assert "my background" not in lowered
    assert "china-born" not in lowered


def test_linkedin_post_mentions_attached_infographic_when_available():
    article = Article(
        title="AI policy shifts in Asia",
        url="https://example.com/ai-policy",
        source="Example",
        summary="A test article.",
    )
    post = generate_linkedin_post(article, infographic_available=True)
    assert "attached a concise NotebookLM infographic" in post.text
