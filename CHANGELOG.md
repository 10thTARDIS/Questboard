# Changelog

All notable changes to Questboard are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

_Nothing yet._

---

## [0.1.1] — 2026-03-14

### Added
- Apple Calendar (`webcal://`) link alongside the existing `.ics` download on
  confirmed sessions — uses `window.location.host` so it works in any deployment
- Dependabot configuration: weekly automated PRs for Python (pip), JavaScript
  (npm), and GitHub Actions dependencies

### Fixed
- `release.yml`: workflow was passing the unstripped tag name (e.g. `v0.1.0`)
  to the Python changelog extractor, causing a lookup miss; now strips the
  leading `v` before matching against `CHANGELOG.md` headings
- Milestone PATCH endpoint: passing only some fields (e.g. just `title`) would
  previously clear all unmentioned nullable columns; endpoint now uses
  `exclude_unset=True` so only explicitly provided fields are written

---

## [0.1.0] — 2026-03-14

First tagged release. Covers all v1.0 scheduling features and the
app-side foundations required for v2.0 Discord bot integration.

### Added — v1.0 Core Scheduling

- **OIDC authentication** — login via any OIDC provider; opaque session
  cookie stored in Redis
- **Campaign management** — create, join (invite code), edit, delete;
  GM and player roles enforced throughout
- **Leave campaign** — players can leave voluntarily; last GM is blocked
  with an error
- **Session scheduling** — three modes:
  - *Vote* — propose 2–5 time slots; players vote availability (yes /
    maybe / no); GM confirms the winner
  - *Direct* — single time, confirmed immediately on creation
  - *Tentative* — single time, GM confirms when ready
- **Vote notifications** — per-campaign GM-configurable setting:
  - `each_vote` — Discord webhook message on every vote cast
  - `all_voted` — single message when all eligible players have voted
- **Vote auto-close** — automatically confirm the top-voted slot after a
  GM-configured number of hours
- **Session time picker** — custom date / 12-hour / 15-min / AM-PM
  component (replaces native `datetime-local`)
- **Calendar exports** — `.ics` download and Google Calendar deep-link
  on confirmed sessions
- **Session status auto-complete** — Celery Beat task (every 5 min)
  transitions confirmed sessions to `completed` once the time passes
- **Session notes** — per-user private notes and GM public notes per
  session; public notes appear in all players' campaign journals
- **Campaign journal** — aggregated view of all sessions with notes,
  ordered chronologically (`/campaigns/:id/notes`)
- **Attendance tracking** — GM marks who attended on completed sessions;
  endpoint already ready for v2 bot auto-detection
- **Configurable reminders** — up to three reminders per campaign, each
  with a value + unit (minutes / hours / days); fired via Celery at the
  scheduled ETAs
- **Per-campaign Discord webhook** — campaign-level webhook with
  global fallback
- **User profiles** — display name override, timezone selector
- **Character names** — per-campaign character name set by each player
- **Admin panel** — user list with last-login, campaign memberships,
  attendance stats; grant/revoke admin role
- **Admin: notification settings** — SMTP configuration (host, port,
  TLS, from address) + global Discord webhook fallback; test-email button
- **First-user admin bootstrap** — Alembic data migration promotes the
  earliest registered user if no admins exist; `make set-admin` CLI
  escape hatch
- **Dark / light theme toggle** — dark default; preference persisted in
  localStorage
- **Next-session countdown** — days / hours / minutes until the next
  confirmed session shown on each campaign card in the dashboard

### Added — v2.0 App-Side Foundations

- **Platform links** — `platform_links` table (already in schema);
  new Profile page "Connected Accounts" section to link / unlink Discord
  and Matrix account IDs; endpoints `GET/POST/DELETE /api/me/platform-links`
- **Bot API key** — admin can generate a `secrets.token_hex(32)` key
  stored in `app_settings`; shown once on generation
- **`require_bot_auth` dependency** — validates `X-Bot-Key` request
  header against the stored key using `secrets.compare_digest`
- **Bot settings admin tab** — Discord bot token, Whisper transcription
  endpoint + key, LLM summarisation endpoint + key + model; blank
  fields preserve existing secrets on save
- **Bot API router** (`/api/bot/`) — all endpoints require `X-Bot-Key`:
  - `GET /bot/sessions/upcoming` — confirmed sessions in next 7 days
  - `GET /bot/campaigns/{id}/linked-users` — members with Discord IDs
  - `PUT /bot/sessions/{id}/timeslots/{slot}/vote` — vote on behalf of
    a Discord user (resolves user via `platform_links`)
  - `PUT /bot/sessions/{id}/attendance/{discord_user_id}` — mark
    attendance on behalf of a Discord user
  - `POST /bot/sessions/{id}/transcript` — upload recording URL,
    transcript, and summary from the bot
- **Transcript & summary display** — `RecordingSection` component in
  `SessionDetail`; shows summary as prose, full transcript collapsible,
  recording URL as an external link; section hidden until bot populates
- **Campaign milestones** — `milestones` table + Alembic migration; GM
  can create / edit / delete milestones with optional description,
  linked session, and date; displayed below Sessions on the campaign
  page in chronological order

---

[Unreleased]: https://github.com/10thTARDIS/Questboard/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/10thTARDIS/Questboard/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/10thTARDIS/Questboard/releases/tag/v0.1.0
