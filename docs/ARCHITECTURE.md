# Architecture

The system is English-first by default and uses Telegram buttons as the main interaction surface.

```mermaid
flowchart LR
    TG["Telegram Bot"] --> API["Backend / Orchestrator"]
    API --> Search["News Search Service"]
    API --> Learning["Learning Package Builder"]
    API --> NLM["NotebookLM Adapter"]
    API --> LinkedIn["LinkedIn Post Generator"]

    Search --> GNews["Google News RSS"]
    Search --> GDELT["GDELT"]
    Search --> NewsAPI["NewsAPI"]
    Search --> CSE["Google Programmable Search"]
    Search --> Tavily["Tavily"]

    Learning --> Sources["Primary News + Deep Context"]
    Sources --> NLM
    NLM --> Artifacts["NotebookLM Link / Audio Overview / Study Guide"]
    Artifacts --> TG
    LinkedIn --> TG
```

## Telegram Button Flow

```mermaid
flowchart TD
    A["/start"] --> B["Main Menu"]
    B --> C["Search News"]
    B --> D["AI & Technology"]
    B --> E["Business & Economy"]
    B --> F["China-Singapore Tech"]
    C --> G["User enters keyword"]
    D --> H["Run Search"]
    E --> H
    F --> H
    G --> H
    H --> I["Top 10 result buttons"]
    I --> J["Select article"]
    J --> K["Generate NotebookLM Learning Pack"]
    K --> L["Return NotebookLM link and status"]
    L --> M["Generate LinkedIn Post"]
    M --> N["Open LinkedIn share page"]
```

## Search Coverage

The search layer intentionally combines several sources:

- Google News RSS for timely headline discovery.
- GDELT for broad global news coverage without an API key.
- NewsAPI for structured news search when an API key is available.
- Google Programmable Search for high-traffic web articles and domain-targeted search.
- Tavily for AI-friendly deep context and long-form article discovery.

The ranking layer scores results by relevance, freshness, source authority, article type, depth, and traffic proxy.

## Personalized Ranking

The default search window is 7 days. Results are additionally weighted toward the user's background: AI, technology deployment, governance, Singapore public-sector technology, China-Singapore collaboration, ASEAN relevance, semiconductors, cloud, data centers, and enterprise adoption.

## NotebookLM Automation

NotebookLM is handled through a dedicated adapter using `notebooklm-py[browser]`:

- Prepare the selected news title, summary, learner context, and original URL.
- Add the selected-news learning guide as a text source.
- Try to add the original publisher URL, but ignore failures caused by paywalls or parser restrictions.
- Run NotebookLM Web Fast Research and import fewer than 20 high-signal sources discovered by NotebookLM.
- Target a 15-minute Deep Dive podcast.
- Generate a shorter Audio Brief for quick listening.
- Generate the Deep Dive podcast, Audio Brief, and portrait/concise infographic in parallel.
- Download all completed NotebookLM media artifacts and return them to Telegram.
- Use a stored Google/NotebookLM `storage_state.json` session on the server.

The adapter keeps NotebookLM isolated from Telegram and search logic, so the connector can be replaced if Google later releases an official API.
