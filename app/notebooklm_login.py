from __future__ import annotations

import os
from pathlib import Path

from app.config import get_settings


NOTEBOOKLM_URL = "https://notebooklm.google.com/"
GOOGLE_ACCOUNTS_URL = "https://accounts.google.com/"
DEFAULT_MAC_CHROME = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
)


def main() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is required. Install notebooklm-py[browser].") from exc

    settings = get_settings()
    storage_path = Path(
        settings.notebooklm_storage_path or ".local/notebooklm-storage/storage_state.json"
    )
    profile_dir = Path(settings.notebooklm_user_data_dir)
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    profile_dir.mkdir(parents=True, exist_ok=True)

    executable_path = os.environ.get("NOTEBOOKLM_CHROME_EXECUTABLE") or _default_chrome_path()
    if not executable_path:
        raise RuntimeError(
            "Could not find a local Chrome executable. Set NOTEBOOKLM_CHROME_EXECUTABLE."
        )

    print("Opening Chrome for NotebookLM login...")
    print(f"Profile directory: {profile_dir}")
    print(f"Storage file: {storage_path}")

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            executable_path=executable_path,
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--password-store=basic",
            ],
            ignore_default_args=["--enable-automation"],
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(NOTEBOOKLM_URL, wait_until="load")

        print("\nInstructions:")
        print("1. Complete Google login in the opened Chrome window.")
        print("2. Wait until you can see the NotebookLM homepage.")
        print("3. Return here and press ENTER to save the session.\n")
        input("[Press ENTER when logged in] ")

        page.goto(GOOGLE_ACCOUNTS_URL, wait_until="load")
        page.goto(NOTEBOOKLM_URL, wait_until="load")
        context.storage_state(path=str(storage_path))
        context.close()

    print(f"NotebookLM session saved: {storage_path}")


def _default_chrome_path() -> str | None:
    candidates = [
        DEFAULT_MAC_CHROME,
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


if __name__ == "__main__":
    main()

