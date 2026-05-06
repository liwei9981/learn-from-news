# Implementation Plan — Refined Learn from News Workflow (v3)

> Last updated: 2026-05-06  
> Status: **Approved — Ready for Implementation**

---

## Summary of Clarifications Applied

| # | User Feedback | Plan Decision |
|---|---|---|
| 1 | Trending = no keyword, broad search for everything trending | Broad multi-topic query, 3-day window, paywall-filtered |
| 2 | Max 2 learning point selections | Confirmed: max 2 |
| 3 | Use Gemini for LinkedIn post (user provides API key) | **Gemini 2.5 Pro** for both LP extraction AND LinkedIn post |
| 4 | Only podcast (15 min) + infographic | Remove audio brief entirely |

---

## Overview of Changes

| Stage | What Changes |
|---|---|
| News Search | Add "📈 Trending Now" button — broad 3-day search, paywall-filtered |
| Article Analysis | New step: extract 5 learning points via Gemini 2.5 Pro |
| Learning Pack | Guide & NotebookLM prompts rebuilt around selected learning points |
| NotebookLM | New research query + prompts for 15-min podcast + portrait infographic only |
| LinkedIn | Gemini-generated 2–3 sentence post, clean copy-paste output |

---

## Phase 1 — Config, Dependencies & Model Updates

### New dependency — `pyproject.toml`
```
google-generativeai>=0.8.0
```

### `app/config.py` — add:
```python
trending_lookback_days: int = Field(default=3, ge=1, le=7)
trending_query: str = "artificial intelligence technology business science geopolitics"
gemini_api_key: str | None = None
gemini_model: str = "gemini-2.5-pro-preview-05-06"
```

### `.env` + `.env.example` — add:
```
GEMINI_API_KEY=         # your Gemini API key goes here
GEMINI_MODEL=gemini-2.5-pro-preview-05-06
```

> Note: `GEMINI_API_KEY` is already saved in `.env`. Do NOT commit `.env` to Git.

### `app/models.py` — add field to `NotebookPackage`:
```python
learning_points: list[str] = Field(default_factory=list)
```

> `trending_query` is a broad catch-all. Google News RSS + GDELT surface whatever is genuinely trending in the past 3 days across all topics.

---

## Phase 2 — New Module: `app/learning/points.py`

Extracts **5 learning points** from an article using **Gemini 2.5 Pro**.

**Prompt design:**
```
You are a learning coach helping a senior technology and policy professional
learn from news articles.

Read this article and identify exactly 5 valuable learning points.
Each point should be a specific concept, person, historical event,
trending idea, or key data point worth understanding more deeply.
Be concise — each point is a short phrase (5–10 words).

Article title: {title}
Summary: {summary}

Return exactly 5 learning points, one per line, numbered 1–5. No extra text.
```

**Fallback:** If Gemini is unavailable or `GEMINI_API_KEY` is not set, extract using a lightweight rule-based approach (capitalised noun phrases from title + summary). This ensures the bot always works even without the API key configured.

> Using Gemini for LP extraction gives dramatically better results than rule-based NLP — it understands context, identifies key people and concepts correctly, and produces clean readable phrases.

---

## Phase 3 — File Updates (non-bot)

### `app/search/providers.py`
- Add `PAYWALL_DOMAINS` frozenset — known paywalled sources:
  - ft.com, wsj.com, economist.com, nytimes.com, bloomberg.com, foreignpolicy.com, hbr.org, theatlantic.com
- Add `filter_paywalled(articles) -> list[Article]` — used only for trending search results
- Trending search uses 3-day lookback + applies paywall filter before ranking

### `app/learning/package.py`
- `build_notebook_package()` gains `learning_points: list[str]` parameter
- Guide markdown restructured into 4 sections:
  1. **Primary News Article** — title, summary, URL
  2. **Selected Learning Points** — numbered list of chosen points
  3. **Learning Objectives** — for each point: explain it, give background, connect to news
  4. **Output Requirements** — podcast spec + infographic spec (see prompts below)

### `app/notebooklm.py` — revised prompts

Remove `_audio_brief_instructions` and all audio brief generation entirely.

**`_research_query(package)`**:
```
Research this news story and the specific learning points the learner has chosen.

News: {title}
Summary: {summary}
Source: {url}

Learning Points to Research:
- {point_1}
- {point_2}

For each learning point, find authoritative, open-access sources that:
- Explain the concept, person, or event in depth
- Provide historical context or background
- Connect it to the news article

Prioritise high-signal, non-paywalled sources.
```

**`_audio_instructions(package)`**:
```
Create an English Deep Dive podcast of exactly {target_minutes} minutes.

Structure:
1. News Brief (2 min) — what happened and why it matters
2. Learning Point Deep Dive — one segment per selected learning point:
   - Explain the concept, person, or event clearly
   - Provide background and historical context
   - Connect it back to the news and its implications
3. Closing (1 min) — how these learning points relate to the bigger picture

Tone: conversational, intellectually engaging, suitable for a senior technology
and policy professional. Avoid generic AI commentary; give sharp, grounded analysis.

Selected learning points: {point_1}, {point_2}
```

**`_infographic_instructions(package)`**:
```
Create a portrait-oriented, concise, professional infographic in English.
Use the CONCISE detail level.

Structure (max 6 blocks):
Section 1 — News Brief:
  Block 1: What Happened (2-3 sentences)
  Block 2: Why It Matters (2-3 sentences)

Section 2 — Learning Points:
  One block per selected learning point:
    - Clear heading (the learning point name)
    - 2-sentence explanation
    - 1-sentence connection to the news

Keep wording simple, clear, and executive-friendly. No dense paragraphs.
Learning points: {point_1}, {point_2}
```

### `app/linkedin.py` — rewrite using Gemini 2.5 Pro

`async def generate_linkedin_post(article, learning_points, api_key, model)` — async Gemini call.

**Prompt design:**
```
Write a LinkedIn post about this news article.

Requirements:
- 2 to 3 sentences only — short, concise, and friendly
- Naturally share the news and bring up the selected learning points
- Write with genuine curiosity and a good learning attitude
- End by inviting people to read the article (woven in, not a separate line)
- No hashtags
- Do NOT include the article URL (added separately)
- First person, natural human tone

News title: {title}
Summary: {summary}

Learning points to highlight:
- {point_1}
- {point_2}
```

**Output format** — bot sends ONE clean Telegram message:
```
{gemini post text}

{article.url}
```

No labels, no preamble. User copies and pastes the whole message directly to LinkedIn.

**Fallback:** If `GEMINI_API_KEY` is not set, generate a simple natural-language post from article title + learning points (string assembly). The user still gets something usable.

---

## Phase 4 — Bot Conversation Flow Refactor (`app/bot.py`)

### Updated Main Menu
```
[🔍 Search News]
[📈 Trending Now]
```

### `context.user_data` Keys
| Key | Type | Purpose |
|---|---|---|
| `awaiting_search` | bool | Waiting for keyword input |
| `articles` | list[Article] | Current search results |
| `selected_article` | Article | Chosen article |
| `learning_points` | list[str] | 5 Gemini-extracted points |
| `selected_lp` | set[int] | Toggled indices (max 2) |
| `selected_learning_points` | list[str] | Final confirmed points |
| `notebooklm_infographic_path` | str | Path for optional LinkedIn attachment |

### Callback Data
| callback_data | Triggers |
|---|---|
| `search` | Ask for keyword |
| `trending` | Run 3-day broad paywall-filtered search |
| `select:{i}` | Pick article i from list |
| `lp_toggle:{i}` | Toggle learning point i (max 2) |
| `lp_confirm` | Lock in selections → start NotebookLM |
| `linkedin` | Generate + send clean LinkedIn post |
| `article_actions` | Go back to article action view |
| `menu` | Return to main menu |

### Full Conversation Flow

```
/start
  └─ MAIN MENU
      ├─ [🔍 Search News]
      │     → "Type a keyword. Example: AI chips"
      │     → User types keyword → _run_search(keyword, 7 days)
      └─ [📈 Trending Now]
            → _run_trending_search(broad_query, 3 days, paywall-filtered)

─────────────────────────────────────────
Article list (up to 10 buttons)
  └─ [Article N] → _show_article_actions(article)
        Shows: title, source, summary, link
        Buttons:
          [🎓 Build Learning Pack]
          [« Start Over]

─────────────────────────────────────────
[🎓 Build Learning Pack]
  → "Analysing article..."
  → extract_learning_points(article)  ← Gemini 2.5 Pro call
  → Show learning point selection UI:

    "What would you like to learn from this news?
     Tap to select up to 2 points.

     ○ 1. <point_a>
     ○ 2. <point_b>
     ✅ 3. <point_c>   (selected)
     ○ 4. <point_d>
     ○ 5. <point_e>

     Selected: 1/2"

    Buttons (one per point, toggle in-place):
    [○ 1. <point_a>]
    [✅ 3. <point_c>]
    ...
    [🎓 Generate Learning Pack]   ← appears once ≥ 1 selected
    [« Back]

─────────────────────────────────────────
[🎓 Generate Learning Pack]
  → "NotebookLM generation started..."
  → _generate_learning_package(article, selected_points)
      build_notebook_package(article, related, learning_points)
      NotebookLMService.create_learning_notebook(package)
        1. Create notebook
        2. Add text guide source (article + learning objectives)
        3. Add primary URL source
        4. Deep Research on learning points (web sources)
        5. Generate in PARALLEL:
           ├─ 15-min podcast (Deep Dive)
           └─ Portrait infographic (Concise)
        6. Download both files
  → Deliver podcast + infographic to Telegram
  → Post-delivery menu:
      [Open NotebookLM]
      [📝 Create LinkedIn Post]
      [Start Over]

─────────────────────────────────────────
[📝 Create LinkedIn Post]
  → generate_linkedin_post(article, selected_learning_points)  ← Gemini 2.5 Pro
  → Bot sends ONE clean message:
      "{natural 2-3 sentence post}

       {article.url}"
  → (No buttons, no labels — just the copy-paste message)
```

---

## Files Changed

| File | Change Type | Key Change |
|---|---|---|
| `pyproject.toml` | Modify | Add `google-generativeai>=0.8.0` |
| `.env` + `.env.example` | Modify | Add `GEMINI_API_KEY`, `GEMINI_MODEL` ✅ done |
| `app/config.py` | Modify | Add `gemini_api_key`, `gemini_model`, `trending_*` |
| `app/models.py` | Modify | Add `learning_points` to `NotebookPackage` |
| `app/learning/points.py` | **New** | Gemini LP extractor + rule-based fallback |
| `app/learning/package.py` | Modify | Accept + embed `learning_points` in guide |
| `app/notebooklm.py` | Modify | New prompts, remove audio brief |
| `app/linkedin.py` | Rewrite | Gemini-generated post + string-assembly fallback |
| `app/search/providers.py` | Modify | Add paywall filter, trending search support |
| `app/bot.py` | Refactor | New menu, LP selection UI, updated callbacks |
