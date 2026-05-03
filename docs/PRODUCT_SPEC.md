# Product Spec

## Default Language

English is the default language for the full product:

- Telegram menus and buttons
- Search queries and query expansion
- News summaries
- NotebookLM learning packages
- Audio Overview prompts
- Infographic text
- LinkedIn post drafts

Chinese is used only when the user explicitly requests it.

## User Persona for LinkedIn

The LinkedIn post generator should reflect this background:

- China-born, based in Singapore for 26 years, deeply localized.
- Strong technology background.
- Former long-term experience in Singapore's government technology sector.
- Currently focused on China-Singapore technology collaboration, especially AI.
- Interested in AI governance, deployment, infrastructure, talent, and regional cooperation.

## MVP Commands and Buttons

- `/start`
- `Personalized 7-Day Brief`
- `Search News`
- `AI & Technology`
- `Business & Economy`
- `China-Singapore Tech`
- `Generate NotebookLM Learning Pack`
- `Generate LinkedIn Post`
- `Open LinkedIn`
- `Main Menu`

## Optimized Discovery Rules

- Search should default to the past 7 days.
- Ranking should prioritize news that is relevant to the user's background:
  - AI deployment and infrastructure
  - technology governance and regulation
  - Singapore public-sector digital transformation
  - China-Singapore technology collaboration
  - ASEAN and regional technology impact
  - semiconductor, cloud, data center, and enterprise AI developments
- After the user selects an article, the bot should immediately return:
  - short plain-English summary
  - source
  - article link
  - next-step buttons

## NotebookLM Output Rules

- The user should not be sent to NotebookLM to manually build the learning pack.
- The system should connect to NotebookLM automatically through the NotebookLM adapter.
- After the user selects one article, NotebookLM should receive the selected article title, summary, learner context, and original URL if available.
- The original URL is optional. If NotebookLM cannot import it, the system should ignore that error and continue.
- NotebookLM should run its own Web Fast Research based on the selected article and import fewer than 20 high-signal discovered sources into the notebook.
- Deep Dive podcast target length: about 15 minutes.
- Audio Brief: generate a shorter spoken summary for quick listening.
- Infographic: portrait orientation, concise content level, clear, easy to understand, and no more than 6 key blocks.
- The implementation route is `notebooklm-py[browser]` with a stored Google/NotebookLM session.
- The system should create a NotebookLM notebook, add the selected-news learning guide as a text source, optionally add the original URL, run NotebookLM Fast Research, then trigger Deep Dive podcast, Audio Brief, and Infographic generation in parallel. It should download all completed files and return them to Telegram.
- The project also generates a local HTML infographic draft as a fallback artifact.
