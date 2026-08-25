# Adabary News Engine

The first two phases supply the local foundation for the Telegram news bot: a FastAPI
service, environment-driven configuration, PostgreSQL in Docker, and a news collector
that normalizes GDELT, curated RSS, and official announcement feeds.

## Quick start

1. Create an untracked `.env` from `.env.example` and replace its password placeholder
   with one local development password in both matching fields.
2. Start PostgreSQL:

   ```powershell
   docker-compose up -d
   ```

3. Activate the virtual environment and run the service:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   uvicorn app.main:app --reload
   ```

4. Open `http://127.0.0.1:8000/health` to confirm the service responds.

5. Preview an on-demand collection without storing it:

   ```text
   http://127.0.0.1:8000/news/collect
   ```

6. After PostgreSQL is running, initialize the schema once and collect into it:

   ```text
   POST http://127.0.0.1:8000/database/setup
   POST http://127.0.0.1:8000/news/collect-and-store
   ```

   The storage endpoint ignores article links that were already collected, including
   versions with common marketing parameters such as `utm_source`.

## Analysis

Phase 4 scores stored articles for relevance, importance, novelty, credibility, and
viral potential. The default `heuristic` provider works without a key. To use OpenAI,
set `ANALYSIS_PROVIDER=openai` plus `AI_API_KEY` and `AI_MODEL` in the untracked `.env`
file, restart the service, then call `POST /articles/{article_id}/analyze`.

## Drafts

Phase 5 creates reviewable Telegram-ready drafts only for recommended articles. Call
`POST /articles/{article_id}/draft` and inspect the result with `GET /drafts`. This phase
does not send anything to Telegram.

## Telegram publishing

Phase 6 uses explicit approval. Add the bot token and channel ID only to the untracked
`.env` file, add the bot as a channel administrator with permission to post, then use
`POST /drafts/{draft_id}/approve-and-publish`. The endpoint records Telegram's message
ID and rejects attempts to publish the same draft twice.

## Scheduling and languages

Phase 7 lets you schedule one draft through `POST /drafts/{draft_id}/schedule` with an
ISO 8601 `scheduled_for` value. Scheduled auto-publishing is disabled by default.
For reader language choice, create separate public channels for English, Amharic, Afaan
Oromo, and Tigrinya, then add their public links to `.env`. `GET /languages/menu` returns
an inline-keyboard-compatible chooser for the bot interface.

Set `SCHEDULER_ENABLED=true` and `AUTO_PUBLISH_SCHEDULED=true` only when you are ready
for scheduled posts to go live. Set `AUTO_PUBLISH_BREAKING=true` only when high-priority
breaking items may bypass manual approval; otherwise inspect candidates at `GET /breaking`.

## Production: free Render + Neon

The included `render.yaml` creates one free public FastAPI web service. Create a Neon
database, copy its pooled PostgreSQL connection string into Render as `DATABASE_URL`, then
deploy this repository as a Render Blueprint. Standard Neon `postgresql://` URLs work
directly. Render requires the web service to bind to `0.0.0.0` and its assigned `PORT`;
the Blueprint does this.

Set these secret environment variables in Render (never commit them):

```text
DATABASE_URL
TELEGRAM_BOT_TOKEN
TELEGRAM_CHANNEL_ID
TELEGRAM_OWNER_CHAT_ID
TELEGRAM_WEBHOOK_SECRET
PUBLIC_BASE_URL
```

After the Render web-service URL is known, set `PUBLIC_BASE_URL` to it and call
`POST /telegram/webhook/setup` once. In a private chat with the bot, send `/start` and
tap **Find news**. The bot offers **Publish now**, **Reject**, **In 1 hour**, and
**In 3 hours** buttons. Only `TELEGRAM_OWNER_CHAT_ID` can invoke those controls.

Free Render web services pause after 15 minutes with no incoming traffic. To keep the
owner bot and in-process scheduler available for a hobby deployment, the repository
includes `.github/workflows/render-keepalive.yml`, which requests `/health` every
13 minutes. After deployment, create the GitHub repository secret
`RENDER_HEALTHCHECK_URL` with the value `https://<your-render-service>/health`.
GitHub's scheduled jobs can be delayed, and free Render services can restart, so this is
not a production availability guarantee. A paid worker is the proper upgrade path when
reliability becomes essential.

## Tests

```powershell
pytest
```

No production or Telegram secrets are included in this phase.
"# adabarynews" 
