# Dasturlash & AI Control Bot

**Private admin command center for the Telegram channel `@dasturlash_ai`.**

The public side is intentionally small: users can pass the channel-subscription check and send a support message to the administrator. AI, channel publishing, scheduling, broadcast, analytics, research, settings and security screens are admin-only.

## Features

- **Public:** `/start`, `/help`, required channel subscription, support tickets with text/photo/video/voice/audio/document, ticket IDs, 30-second anti-spam, daily ticket-creation cap and user ban checks.
- **Admin access:** owner IDs from `ADMIN_IDS`, router-level `AdminFilter`, plus an in-handler identity check for callbacks. Non-admins receive the generic `Buyruq topilmadi` response for hidden admin commands/callbacks.
- **AI Prompt Studio:** categorized prompt generation, regenerate/improve/shorten/translate, prompt library and prompt-to-channel draft.
- **Content Studio:** three AI post variants, Terminal/Card/Minimal/Script styles, six heading fonts, preview, edit, publish and schedule.
- **Channel automation:** one-time/daily/weekly posts, persisted schedule records restored from PostgreSQL, one configurable reaction after publish.
- **Support:** inbox, ticket history, reply with text or media, status, tag, important flag and ban action.
- **Admin tools:** research (optional Tavily), analytics, growth chart, AI usage counters, broadcast segments, user lookup, backup, audit log, health check and emergency switches.
- **Storage:** PostgreSQL is the durable source of truth; Redis is for FSM/cache/rate limiting only.
- **Hosting:** Render-compatible HTTPS webhook, `/health` endpoint for UptimeRobot, local polling and Docker Compose for development.

## Important platform limits

Telegram chat text does not support arbitrary font colors. The hacker look is created with emoji, Unicode terminal blocks, monospace HTML, short animated edits and dark neon PNG charts. All buttons are genuine Telegram inline keyboard buttons and are never embedded in HTML.

A non-Premium bot can set at most one reaction on a message. Reaction availability depends on the channel's allowed-reaction configuration. The bot must be a channel administrator to check membership and receive channel membership/reaction-count updates. See the [Telegram Bot API](https://core.telegram.org/bots/api).

Render Free is intended for testing/hobby projects, not guaranteed production uptime. Free web services spin down after 15 minutes without inbound traffic, have ephemeral filesystems and can restart; each workspace receives 750 free instance hours per calendar month. A five-minute UptimeRobot monitor may keep a single service active for roughly 720–744 hours in a 30–31 day month, leaving little headroom and still providing no uptime guarantee. Free Render Postgres expires 30 days after creation. Use a managed external PostgreSQL such as Neon for persistent data and take regular backups. UptimeRobot checks `/health` every five minutes on its Free plan. Upstash Free Redis currently lists a 256 MB data limit and 500,000 monthly commands; quotas and product terms can change. Redis is for transient FSM/cache/rate-limit data only; do not store important business records in it.

## AI models and cost estimates

The defaults are `gpt-5.4-mini` (OpenAI) and `claude-sonnet-5` (Anthropic). Model IDs can change; verify the provider dashboard before deployment. The `.env` file exposes per-million-token input/output estimate rates. The estimate is approximate and may differ with cached tokens, tools, regional inference, and provider billing. Update the rates when changing model or billing tier.

## Requirements

- Python 3.11+
- Telegram bot token from `@BotFather`
- A Telegram channel where the bot is an administrator with post/edit/delete permissions
- PostgreSQL 15+ (Neon recommended for the free-tier example)
- Redis-compatible URL (Upstash Redis recommended for the free-tier example)
- OpenAI or Anthropic API key
- Optional Tavily API key for live research

## Local setup (polling)

1. Create a bot using `@BotFather` and copy its token.
2. Add the bot as an administrator to `@dasturlash_ai`; grant **Post Messages**, **Edit Messages**, and **Delete Messages**. Membership checks require the bot to be a channel administrator.
3. Find the numeric channel ID. You can use the included helper after setting `BOT_TOKEN`:

   ```bash
   python scripts/get_channel_id.py
   ```

   Send a channel post after the helper is running, or use a trusted Telegram update inspector. Do not publish the bot token.
4. Create PostgreSQL and Redis databases. Copy their connection URLs.
5. Create the environment file and populate every required value:

   ```bash
   cp .env.example .env
   ```

6. Install dependencies and run:

   ```bash
   python -m venv .venv
   # Linux/macOS:
   source .venv/bin/activate
   # Windows PowerShell:
   # .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

7. Set `BOT_MODE=polling` for local development, then:

   ```bash
   python -m bot.main
   ```

8. Send `/start` from the owner account, then `/admin`.

## Render Free + Neon + Upstash + UptimeRobot

### 1. PostgreSQL on Neon

- Create a Neon project and database.
- Copy the PostgreSQL connection string. Use the pooled connection string if the Neon dashboard recommends it for your service.
- Keep the password private. Add the URL to Render as `DATABASE_URL`.
- Export/backup the database regularly. The bot also supports a JSON logical backup delivered to `BACKUP_CHAT_ID`.

### 2. Redis on Upstash

- Create a Redis database in Upstash. Check the current free-plan limits before deploying because request/storage quotas can change.
- Copy its TLS connection URL (`rediss://...`) into Render as `REDIS_URL`.
- Redis is used for aiogram FSM, 60-second subscription cache and anti-spam counters. PostgreSQL retains users, tickets, posts, jobs, events and settings.

### 3. Deploy on Render

- Push this project to a private/public Git repository.
- In Render choose **New → Blueprint** and select the repository (the supplied `render.yaml` configures a Free web service).
- Add secrets in Render Environment:
  - `BOT_TOKEN`
  - `ADMIN_IDS` (comma-separated numeric Telegram IDs)
  - `CHANNEL_ID` (for example `-1001234567890`)
  - `DATABASE_URL` (Neon)
  - `REDIS_URL` (Upstash)
  - `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`
  - `WEBHOOK_SECRET` (at least 32 characters using only letters, digits, `_`, `-`)
- Keep `BOT_MODE=webhook`. Render provides `RENDER_EXTERNAL_URL`; otherwise set `WEBHOOK_BASE_URL` to the deployed HTTPS service URL.
- Wait for deployment. Visit `https://YOUR-SERVICE.onrender.com/health`; expected JSON has `status: ok`.

### 4. UptimeRobot

- Create an HTTP(s) monitor in UptimeRobot.
- Monitor URL: `https://YOUR-SERVICE.onrender.com/health`.
- Select the Free plan's five-minute interval.
- This is availability monitoring and may help keep inbound traffic flowing, but it is not a contractual uptime guarantee. Render can still restart or suspend a Free service.

### 5. Telegram webhook verification

- On startup the bot calls `setWebhook` with `WEBHOOK_SECRET`.
- Telegram sends `X-Telegram-Bot-Api-Secret-Token`; the HTTP endpoint verifies it with a constant-time comparison.
- `allowed_updates` includes `message`, `callback_query`, `chat_member`, `my_chat_member`, and `message_reaction_count`.
- Do not run polling and webhook at the same time for the same bot token.

## Docker Compose (local services)

The compose file starts PostgreSQL, Redis and the bot. Keep `BOT_MODE=polling` for local use and fill `.env` with a valid bot token, admin IDs, channel ID and AI key.

```bash
docker compose up --build -d
docker compose logs -f bot
```

Stop services:

```bash
docker compose down
```

PostgreSQL data is stored in the named Docker volume `postgres_data`.

## Uptime / backup notes

- `/health` reports database connectivity and Redis/fallback state.
- Daily logical backup is sent to `BACKUP_CHAT_ID` (default: the lowest numeric ID in `ADMIN_IDS`). Set `BACKUP_CHAT_ID` explicitly if you want another admin chat.
- Render Free local files are ephemeral. Do not rely on local logs, PNGs or files surviving a redeploy/sleep/restart. Charts are generated in memory; backup files are sent to Telegram.
- APScheduler job definitions are stored in PostgreSQL and restored after restart. A free service that is asleep cannot publish at the exact scheduled second; after wake-up, a missed one-time publication may run late. For strict timing, use an always-on worker/paid service or an external durable queue.

## Security checklist

- Never commit `.env` or paste bot/API tokens into source files.
- Keep `ADMIN_IDS` restricted to trusted owner accounts.
- Keep the bot an administrator only in the intended channel.
- Review the `Security Center` emergency switches before enabling workflows.
- AI output is sanitized before being sent with Telegram HTML parse mode.
- For public-facing text, escape user-provided HTML. Buttons are separate `InlineKeyboardMarkup` objects.
- Backups contain personal data (user IDs and support messages); keep the receiving Telegram account private and rotate/restrict access as needed.

## Manual test checklist

1. Non-admin `/admin` receives only `Buyruq topilmadi`.
2. Non-admin callback with `adm:`, `ai:`, `post:`, `set:`, `ticket:`, `schedule:`, `broadcast:`, `tool:`, `analytics:`, `users:`, `research:` or `security:` prefix receives the generic response.
3. Unsubscribed user sees the subscription screen; subscribed user sees only the contact button.
4. Text/photo/video/voice/document support messages create a ticket and arrive at admins.
5. Admin can reply with text and media; the user receives the reply.
6. AI prompt generation and prompt-to-channel draft work with a valid provider key.
7. Post preview, style, font, publish, reactions and scheduling work in a test channel.
8. Restart the service and verify scheduled jobs are restored from PostgreSQL.
9. Broadcast uses a test segment and test audience; test cancellation before a large send.
10. Check `/health`, backup delivery, audit log and admin settings.

## English summary

This is an admin-controlled Telegram channel command center. Regular users can only pass mandatory subscription and contact the administrator. AI, publishing, reactions, scheduling, broadcasts, analytics, research and system controls are private admin features. PostgreSQL stores durable data; Redis stores temporary FSM/cache/rate-limit data. Render webhook deployment, Neon Postgres, Upstash Redis and UptimeRobot `/health` monitoring are documented above. Free hosting has sleep/restart/quota limits and must not be treated as guaranteed production infrastructure.
