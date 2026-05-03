# Learn from News

Telegram-first learning system for discovering news, building a NotebookLM learning package, and generating a concise LinkedIn post.

The product is English-first by default. Chinese is used only when explicitly requested.

## MVP Flow

1. User opens the Telegram bot and taps a menu button.
2. User searches a topic or selects a predefined domain.
3. System returns Top News and Deep Context sources.
4. User selects an article.
5. System prepares a NotebookLM source package.
6. NotebookLM generates learning artifacts.
7. Telegram returns NotebookLM links, podcast/audio, infographic links, and key concepts.
8. System generates a short LinkedIn post aligned with the user's China-Singapore AI collaboration background.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Run tests:

```bash
python3 -m pytest
```

Run the Telegram bot:

```bash
python3 -m app.bot
```

Run the API service:

```bash
uvicorn app.main:app --reload
```

## NotebookLM Server Connector

This project uses the unofficial `notebooklm-py[browser]` route for NotebookLM automation. It is server-friendly because the bot reads a stored Google/NotebookLM session instead of relying on visible desktop clicks.

Create the stored session once:

```bash
source .venv/bin/activate
python3 -m app.notebooklm_login
```

Then set:

```bash
NOTEBOOKLM_ENABLED=true
NOTEBOOKLM_STORAGE_PATH=.local/notebooklm-storage/storage_state.json
NOTEBOOKLM_AUDIO_TIMEOUT_SECONDS=1800
NOTEBOOKLM_INFOGRAPHIC_TIMEOUT_SECONDS=1800
```

Verify the session:

```bash
python3 -m app.notebooklm_check
```

## Current Status

This repository contains the MVP architecture and deterministic fallback behavior. Real providers can be enabled by adding API keys to `.env`.

For server deployment notes, see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).
