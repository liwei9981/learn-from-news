from app.bot import _build_delivery_items
from app.models import NotebookResult


def test_delivery_items_are_sent_small_to_large():
    result = NotebookResult(
        infographic_path="infographic.png",
        audio_brief_path="audio-brief.mp3",
        audio_path="podcast.mp3",
    )

    items = _build_delivery_items(result)

    assert [item.label for item in items] == ["infographic", "audio brief", "podcast"]
    assert [item.kind for item in items] == ["photo", "audio", "audio"]
