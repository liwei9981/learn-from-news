import pytest

from app.config import get_settings
from app.learning.package import build_notebook_package
from app.models import Article
from app.notebooklm import NotebookLMService


@pytest.mark.asyncio
async def test_notebooklm_disabled_returns_clear_status(monkeypatch):
    monkeypatch.setenv("NOTEBOOKLM_ENABLED", "false")
    get_settings.cache_clear()
    article = Article(
        title="Singapore and China expand AI collaboration",
        url="https://example.com/ai",
        source="Example",
        summary="A short article summary.",
    )
    package = build_notebook_package(article, [])
    result = await NotebookLMService().create_learning_notebook(package)
    assert result.status == "notebooklm_disabled"
    assert "NOTEBOOKLM_ENABLED=true" in result.notes
    get_settings.cache_clear()
