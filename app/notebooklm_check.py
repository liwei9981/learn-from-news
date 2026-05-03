from __future__ import annotations

import asyncio

from app.config import get_settings


async def check_notebooklm_session() -> None:
    from notebooklm import NotebookLMClient

    settings = get_settings()
    client_context = await NotebookLMClient.from_storage(settings.notebooklm_storage_path)
    async with client_context as client:
        notebooks = await client.notebooks.list()
        print(f"NotebookLM session ok. Found {len(notebooks)} notebooks.")


def main() -> None:
    asyncio.run(check_notebooklm_session())


if __name__ == "__main__":
    main()

