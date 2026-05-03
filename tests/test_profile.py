from app.profile import clean_article_summary, persona_interest_score, summarize_article_for_telegram


def test_persona_interest_score_rewards_ai_singapore_china_terms():
    score = persona_interest_score("Singapore and China expand AI governance collaboration")
    assert score > 0.5


def test_summary_is_shortened_for_telegram():
    summary = summarize_article_for_telegram("Title", "word " * 200)
    assert len(summary) <= 900
    assert "..." in summary


def test_summary_expands_short_text_to_paragraph():
    summary = summarize_article_for_telegram("AI policy shifts in Asia", "A short update.")
    assert summary.count(".") >= 4


def test_clean_article_summary_removes_google_news_html():
    raw = (
        '<a href="https://news.google.com/rss/articles/abc" target="_blank">'
        "China moves to block tech firms</a>&nbsp;&nbsp;<font color=\"#6f6f6f\">"
        "the-decoder.com</font>"
    )
    cleaned = clean_article_summary(raw)
    assert "<a href" not in cleaned
    assert "&nbsp;" not in cleaned
    assert "China moves to block tech firms" in cleaned
