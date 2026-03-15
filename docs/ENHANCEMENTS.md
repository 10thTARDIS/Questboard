# Quest Board — Enhancement Backlog

Tracked future improvements that are out of scope for current releases.
Each entry includes a description, implementation notes, and a priority score
(1 = highest, 5 = lowest).

---

## Integrations

### FoundryVTT Character Sheet Integration

**Priority: 3**

**Description:**
Pull character sheet data directly from an active FoundryVTT world so players
don't have to manually paste a URL. Each campaign member's sheet would be
fetched via the FoundryVTT API and displayed (or deep-linked) on the campaign
member list.

**How to implement:**
1. Expose a FoundryVTT REST API endpoint — either via the
   [foundry-rest-api](https://github.com/foundryvtt/foundryvtt-rest) module or
   a custom lightweight module that wraps `game.actors` with HTTP authentication.
2. Add a per-campaign "FoundryVTT server URL" and "API key" setting (stored in
   `app_settings`, similar to the existing Whisper/LLM config).
3. Add a background Celery task (or on-demand fetch) that queries
   `GET <foundry_url>/api/actors?name=<character_name>` and stores the response
   JSON in a new `character_sheet_data` JSONB column on `campaign_members`.
4. In the frontend, render the key fields from the JSONB blob (class, level, HP,
   etc.) in a tooltip or expandable panel on the member row.
5. A manual URL fallback (already implemented in v0.3.1) should remain for
   players not using FoundryVTT.

**Dependencies:** `character_sheet_url` column from v0.3.1; FoundryVTT instance
must be network-accessible from the Quest Board server.

---

## Bot Features

### Matrix/Element Bot Parity

**Priority: 4**

**Description:**
Replicate all Discord bot features (reaction-based voting, session recording,
attendance detection, account linking) via the Matrix protocol so groups that
use Element/Matrix instead of Discord get the same experience.

**How to implement:**
1. Build a separate `questboard-matrix-bot` service (Python with
   [matrix-nio](https://github.com/poljar/matrix-nio) or
   [mautrix-python](https://github.com/mautrix/python)).
2. The existing `/api/bot/` endpoints in Quest Board already support any
   platform — no backend changes needed beyond ensuring `platform_links`
   entries with `platform="matrix"` are handled throughout.
3. Implement the same event loop as the Discord bot: listen for reactions on
   vote messages → call `PUT /api/bot/sessions/{id}/timeslots/{slot}/vote`.
4. Session recording requires a Matrix voice bridge (e.g. Element Call) with
   an audio stream accessible to the bot — significantly harder than Discord's
   `VoiceClient`.
5. Add a "Matrix Server URL" and "Bot Token" to Admin → Bot Settings
   (new `app_settings` keys).

**Dependencies:** Discord bot (v0.2.x) should be stable before investing in
Matrix parity. Matrix voice recording is a long-term research item.

---

## UX / Frontend

### Shareable Campaign Analytics Link

**Priority: 3**

**Description:**
Allow GMs to generate a public share link for the analytics page so players
can view stats without logging in (e.g. to share with prospective members).

**How to implement:**
1. Add a `analytics_share_token` column (nullable Text, unique) to `campaigns`.
2. Add a GM action in CampaignDetail to generate/revoke the token
   (`POST /api/campaigns/{id}/analytics/share-token`).
3. Add a public endpoint `GET /public/campaigns/{share_token}/analytics` that
   returns the same aggregated data without auth, using the token as a lookup key.
4. Display the share URL in the analytics page header for GMs.

---

## Admin / Operations

### Automated Database Backup Integration

**Priority: 2**

**Description:**
Provide an optional built-in backup mechanism so self-hosters don't need to
configure external tooling. A scheduled Celery Beat task could dump the
database to a configurable destination (local file, S3-compatible object
storage, SFTP).

**How to implement:**
1. Add backup configuration to Admin → Settings: destination type (local/S3),
   credentials, schedule (cron string), retention count.
2. Add a Celery Beat periodic task that runs `pg_dump` in a subprocess and
   uploads the result.
3. Store backup run history (timestamp, size, status) in a new `backup_log` table
   so admins can see the last-successful backup at a glance.
4. Add a "Run backup now" button in the admin panel.

**Dependencies:** Celery Beat is already running. Requires the Postgres
container to have `pg_dump` available, or use SQLAlchemy serialization as a
lighter alternative.

---

### Email Digest / Weekly Summary

**Priority: 4**

**Description:**
A weekly opt-in digest email listing upcoming sessions, recent completions,
and any unresolved vote-mode sessions across all campaigns the user belongs to.

**How to implement:**
1. Add `digest_email_opt_in` boolean to `User` (alongside the existing
   `recap_email_opt_in`).
2. Add a weekly Celery Beat task (Monday 08:00 UTC) that builds per-user
   digests from campaign + session data and sends via the existing SMTP backend.
3. Add the opt-in toggle to the Profile page.
