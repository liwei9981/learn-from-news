# External Services Setup

This project is English-first by default. Keep all service names, bot menus, prompts, and generated learning content in English unless Chinese is explicitly requested.

## 1. Telegram Bot

Purpose: the main user interface for searching news, selecting articles, receiving NotebookLM learning materials, and preparing LinkedIn posts.

Steps:

1. Open Telegram.
2. Search for the verified `@BotFather`.
3. Send `/newbot`.
4. Choose a display name, for example `Learn From News`.
5. Choose a unique username ending in `bot`, for example `LearnFromNewsAIBot`.
6. Copy the bot token.
7. Add it to `.env`:

```bash
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
```

Optional BotFather setup:

```text
/setdescription
AI-powered news learning assistant using NotebookLM.

/setabouttext
Search news, learn key concepts, generate NotebookLM materials, and draft LinkedIn posts.

/setcommands
start - Open main menu
```

Run locally:

```bash
source .venv/bin/activate
python3 -m app.bot
```

## 2. NewsAPI

Purpose: structured news search, latest articles, source filtering, and popularity sorting.

Steps:

1. Create a NewsAPI account.
2. Get an API key.
3. Add it to `.env`:

```bash
NEWS_API_KEY=your_newsapi_key
```

The project can run without this key because Google News RSS and GDELT are already included, but NewsAPI improves structured results.

## 3. Google Programmable Search

Purpose: broader web search for high-traffic articles, long-form analysis, and domain-targeted searches.

Steps:

1. Create a Programmable Search Engine.
2. Configure it to search the entire web, or restrict it to trusted domains.
3. Copy the Search Engine ID. This is the `cx` value.
4. Create a Google API key with Custom Search JSON API enabled.
5. Add both values to `.env`:

```bash
GOOGLE_CSE_API_KEY=your_google_api_key
GOOGLE_CSE_ID=your_search_engine_id
```

Recommended trusted domains:

```text
reuters.com
apnews.com
bbc.com
cnn.com
ft.com
economist.com
bloomberg.com
techcrunch.com
theverge.com
wired.com
technologyreview.com
semianalysis.com
brookings.edu
rand.org
oecd.org
imf.org
worldbank.org
arxiv.org
substack.com
medium.com
```

## 4. Tavily

Purpose: AI-friendly search and deep context discovery. Useful for long-form articles, reports, technical blogs, and source text extraction.

Steps:

1. Create or sign in to a Tavily account.
2. Create an API key in the Tavily dashboard.
3. Add it to `.env`:

```bash
TAVILY_API_KEY=your_tavily_key
```

Recommended use:

- Use Google News RSS and NewsAPI for hot news.
- Use Tavily for deep context sources that will be sent to NotebookLM.

## 5. NotebookLM

Purpose: generate the actual learning package, including Audio Overview, briefing, FAQ, study guide, and source-grounded explanations.

Current MVP setup:

```bash
NOTEBOOKLM_BASE_URL=https://notebooklm.google.com
NOTEBOOKLM_USER_DATA_DIR=.local/notebooklm-browser
NOTEBOOKLM_AUTOMATION_ENABLED=false
PODCAST_TARGET_MINUTES=15
```

Recommended server-first automation approach:

1. Install `notebooklm-py[browser]`.
2. Create a stored Google/NotebookLM session once.
3. Copy the resulting `storage_state.json` to the server.
4. Let the bot use `NotebookLMClient.from_storage()` to create notebooks and generate artifacts.
5. Automatically create a notebook.
6. Add the selected-news title, summary, learner context, and optional URL as a text source.
7. Try to add the original publisher URL. If it fails, continue.
8. Run NotebookLM Web Fast Research and import fewer than 20 NotebookLM-discovered sources.
9. Trigger NotebookLM media generation in parallel:
   - 15-minute Deep Dive podcast
   - short Audio Brief
   - concise infographic
10. Download the generated media files.
11. Return the files to Telegram.

Login/session setup:

```bash
source .venv/bin/activate
python3 -m app.notebooklm_login
```

After login, configure `.env`:

```bash
NOTEBOOKLM_ENABLED=true
NOTEBOOKLM_STORAGE_PATH=.local/notebooklm-storage/storage_state.json
NOTEBOOKLM_AUDIO_TIMEOUT_SECONDS=1800
NOTEBOOKLM_INFOGRAPHIC_TIMEOUT_SECONDS=1800
NOTEBOOKLM_SOURCE_WAIT_SECONDS=180
NOTEBOOKLM_OUTPUT_DIR=Output files
NOTEBOOKLM_MAX_SOURCES=10
```

Verify the stored session:

```bash
source .venv/bin/activate
python3 -m app.notebooklm_check
```

To enable the NotebookLM connector after the first login/session setup:

```bash
NOTEBOOKLM_ENABLED=true
```

Important source rules:

- NotebookLM supports Web URLs, Google Docs, PDFs, pasted text, audio files, and YouTube URLs.
- Web URL imports use text content only.
- Paywalled pages may not import correctly.
- Up to 50 sources can be included in a notebook.

## 6. LinkedIn Sharing

Purpose: generate a concise 2-3 sentence point of view and help publish it with the original news link.

MVP approach:

1. Generate the LinkedIn text inside Telegram.
2. Show the original article URL.
3. Provide an `Open LinkedIn` button using:

```text
https://www.linkedin.com/sharing/share-offsite/?url=ARTICLE_URL
```

Important limitation:

LinkedIn's share page is reliable for sharing the article URL, but it does not reliably prefill the full commentary text. The MVP should show the generated text in Telegram so the user can copy it, then open LinkedIn and paste it.

Production option:

Use LinkedIn OAuth and official posting APIs only if direct one-click posting becomes necessary. This is more complex and may require LinkedIn permissions and app review.

## 7. Local Verification

After adding keys to `.env`, run:

```bash
source .venv/bin/activate
python3 -m pytest
python3 -m app.bot
```

Quick search test:

```bash
source .venv/bin/activate
python3 - <<'PY'
import asyncio
from app.models import SearchRequest
from app.search.service import NewsSearchService

async def main():
    bundle = await NewsSearchService().search(SearchRequest(query="AI chips", max_results=5))
    for item in bundle.top_news[:5]:
        print(item.article.title, item.article.url)

asyncio.run(main())
PY
```

## 8. Security Rules

- Never commit `.env`.
- Never share bot tokens or API keys in screenshots.
- If a key is exposed, revoke it immediately and create a new one.
- Use separate development and production keys where possible.
