# Deployment

This project is designed to run outside Codex, on a normal server, VPS, or container host.

Codex is only a development environment. It may restrict process inspection, browser launch permissions, access to `~/Library`, or long-running background processes. Production should not depend on Codex.

## Recommended Server Setup

- Ubuntu VPS or similar Linux server
- Python 3.11+
- Redis/PostgreSQL later when background workers and history are added
- A persistent project directory or Docker volume
- Environment variables loaded from `.env`

## Run the Bot

```bash
cd "/path/to/16_Learn from News"
source .venv/bin/activate
python3 -m app.bot
```

For production, run it under `systemd`, Docker Compose, or a process manager such as `supervisord`.

## NotebookLM Session

The NotebookLM connector uses `notebooklm-py[browser]` with a stored Playwright session file.

On a desktop machine, initialize the session once:

```bash
source .venv/bin/activate
python3 -m app.notebooklm_login
```

This creates:

```text
.local/notebooklm-storage/storage_state.json
```

On a server, copy this file to a persistent private path and configure:

```bash
NOTEBOOKLM_ENABLED=true
NOTEBOOKLM_STORAGE_PATH=.local/notebooklm-storage/storage_state.json
```

Then verify:

```bash
python3 -m app.notebooklm_check
```

## Security

- Treat `storage_state.json` like a password because it contains Google session cookies.
- Do not commit `.env` or `.local/`.
- Store secrets in server environment variables or a private secrets manager.
- If the Google session expires, rerun `python3 -m app.notebooklm_login` on a desktop environment and replace the server session file.

