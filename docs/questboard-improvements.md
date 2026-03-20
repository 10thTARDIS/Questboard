# Quest Board Improvement Backlog

Improvements to the Quest Board backend that would make the bot richer or more
resilient. Items here are not blocking — the bot works without them — but each
one is worth doing at some point.

**Note for bot-side work:** All Quest Board API changes described below are
already deployed. The remaining work in each item is entirely on the bot side.

---

## How to add an entry

Copy the template below, fill it in, and insert it in priority order (lowest
number first). Keep descriptions factual and brief. If an item is implemented,
delete it from this document rather than marking it done.

```markdown
## <Short title>

**Description:** What is missing or suboptimal, and what effect does it have
on the bot right now.

**How to add:** Which file(s) to change and roughly what the change is.
Keep this to 2–4 sentences — enough to act on without needing to re-research.

**Priority:** N / 5
```

---

## Session title in confirmed and reminder embeds

**Description:** Quest Board now includes `title` and `campaign_name` in the
`extra` field of `session_confirmed` and `session_reminder` bot notify payloads.
The bot's `_handle_confirmed` and `_handle_reminder` handlers do not yet read
these fields, so embeds still display a generic title.

**How to add (bot):** In `bot/cogs/notifications.py`, update `_handle_confirmed`
and `_handle_reminder` to read `extra.get("title")` and
`extra.get("campaign_name")` and include them in the embed title/description.

**Priority:** 2 / 5

---

## Session title and description in timeslots API client

**Description:** `GET /api/bot/sessions/{session_id}/timeslots` now returns
`title` and `description` fields alongside `campaign_name` and `game_system`.
The bot's `SessionTimeslotsResponse` dataclass does not yet include these
fields, so they are silently dropped.

**How to add (bot):** In `bot/api_client.py`, add `title: str | None` and
`description: str | None` to `SessionTimeslotsResponse`. Use them in the
notifications cog when announcing vote sessions and in the recording cog when
announcing that recording has started.

**Priority:** 2 / 5

---

## vote_update embed handler

**Description:** Quest Board now fires `event_type: "vote_update"` to the bot's
`/notify` endpoint (with `session_id`, `guild_id`, `channel_id`, and
`extra = {mode, voter_name, title, campaign_name}`) whenever a vote is cast on
a bot-connected campaign. The bot has no handler for this event type, so the
rich vote-count embed is never displayed.

**How to add (bot):** In `bot/cogs/notifications.py`, add a
`_handle_vote_update(payload)` method. Post an embed to the notification channel
showing the session title, the voter name (from `extra["voter_name"]`), and
up-to-date per-slot yes/maybe/no tallies fetched from
`GET /api/bot/sessions/{session_id}/timeslots`.

**Priority:** 3 / 5

---

## /unlink command — call API directly

**Description:** `DELETE /api/bot/platform-links/discord/{discord_user_id}` now
exists and requires only `X-Bot-Key`. The `/unlink` slash command stub currently
redirects users to their Quest Board profile page instead of using this endpoint.

**How to add (bot):** In `bot/cogs/linking.py`, update the `/unlink` handler to
call `DELETE /api/bot/platform-links/discord/{discord_user_id}`. On 200, confirm
success in a DM; on 404, tell the user their account was not linked.

**Priority:** 3 / 5

---

## session_completed event handler

**Description:** Quest Board now fires `event_type: "session_completed"` to the
bot when a session auto-transitions from `confirmed` to `completed` (Celery Beat
task, runs every 5 minutes). Payload includes `session_id`, `guild_id`,
`channel_id`, and `extra = {title, campaign_name}`. The bot has no handler for
this event.

**How to add (bot):** In `bot/cogs/notifications.py`, add a
`_handle_session_completed(payload)` method. Post a brief embed noting the
session is over. If `session.transcript_updated_at` is null (check via
`GET /api/bot/sessions/{session_id}/summary`), prompt the GM to run `/record`
to upload the transcript.

**Priority:** 4 / 5

---

## /next command — guild-scoped next session

**Description:** `GET /api/bot/guilds/{guild_id}/next-session` now exists.
Returns `{session_id, campaign_id, campaign_name, game_system, title,
confirmed_time}` or 404. Required for bot v0.9.0's `/next` slash command.

**How to add (bot):** Implement the `/next` slash command. Call
`GET /api/bot/guilds/{guild_id}/next-session` using the guild ID from the
interaction context. Format and post an embed with the session details; handle
404 gracefully ("No upcoming session found").

**Priority:** 2 / 5

---

## /recap command — session summary

**Description:** `GET /api/bot/sessions/{session_id}/summary` now exists.
Returns `{session_id, campaign_name, title, confirmed_time, summary,
session_notes}`. Both `summary` and `session_notes` may be null. Required for
bot v0.9.0's `/recap` slash command.

**How to add (bot):** Implement the `/recap` slash command (accepts an optional
session ID; defaults to the most recently completed session for the guild via
`/guilds/{guild_id}/sessions/history?limit=1`). Fetch the summary endpoint and
post an embed; handle null summary gracefully ("No recap available yet").

**Priority:** 2 / 5

---

## /note command — create session note

**Description:** `POST /api/bot/sessions/{session_id}/notes` now exists.
Accepts `{discord_user_id, note}`, resolves to a Questboard user via platform
link, and upserts a private `SessionNote` (appending on a new line if one
already exists). Required for bot v0.9.0's `/note` slash command.

**How to add (bot):** Implement the `/note` slash command. Prompt the user for
note text (modal or argument), then POST to the endpoint with the user's Discord
ID and note content. Confirm success in an ephemeral reply; on 404 (not linked),
prompt them to run `/link` first.

**Priority:** 2 / 5

---

## /ask command — session history for Q&A

**Description:** `GET /api/bot/guilds/{guild_id}/sessions/history?limit=N` now
exists. Returns up to 20 completed sessions where `summary IS NOT NULL`, ordered
`confirmed_time DESC`, as `[{session_id, title, confirmed_time, summary}]`.
Required for bot v0.10.0's `/ask` command.

**How to add (bot):** Implement the `/ask` slash command. Fetch the history
endpoint (limit=10), build a context string from the summaries, send it plus the
user's question to the configured LLM endpoint (from `GET /api/bot/settings`),
and post the answer as an embed. Handle the case where no summaries exist yet.

**Priority:** 3 / 5
