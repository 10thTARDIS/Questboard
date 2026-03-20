# Quest Board — Web App

Self-hosted TTRPG session scheduling tool. Players vote on proposed time slots,
the GM confirms the winner, and the group gets reminded via Discord before every
session. A companion Discord bot (separate package in this monorepo) handles
reaction-based voting and session recording.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend API | Python 3.12, FastAPI 0.115, SQLAlchemy 2 (async), Pydantic v2 |
| Database | PostgreSQL 16, Alembic migrations |
| Async driver | asyncpg |
| Task queue | Celery 5 + Redis 7 (broker on db 1, results on db 2) |
| Auth | Generic OIDC via authlib (Authentik, Keycloak, Google, etc.) |
| Sessions | Redis (db 0), server-side, opaque cookie |
| Frontend | React 18, Vite 6, Tailwind 3, react-router-dom 6 |
| Container | Docker Compose — dev (bind mounts) and prod (pre-built images) |

TLS is terminated externally. Do **not** add TLS/cert logic to this project.

---

## Repository layout

```
backend/
  app/
    auth/           # OIDC flow, Redis sessions, auth dependencies
    middleware/     # Security headers
    models/         # SQLAlchemy ORM models (one file per table)
    notifications/  # Discord webhook + email backends
    routers/        # FastAPI routers (one file per resource)
    schemas/        # Pydantic request/response schemas
    services/       # Business logic (one file per domain)
    tasks/          # Celery tasks (reminder_tasks.py is the main one)
    config.py       # Pydantic Settings singleton (`settings`)
    database.py     # Async engine, AsyncSessionLocal, Base, get_db()
    main.py         # App factory, middleware, router registration
  alembic/
    versions/       # Migration files (never edit existing ones)
  requirements.txt
  requirements-dev.txt
  Dockerfile        # Multi-stage: development / production

frontend/
  src/
    api/            # Fetch wrappers (one file per resource)
    components/     # Shared UI components
    hooks/          # useAuth, useTheme
    pages/          # One file per route
  nginx.conf        # Production: serves SPA + proxies /api and /auth
  Dockerfile        # Multi-stage: development / builder / production (nginx)

postgres/
  init.sql          # Creates questboard_migrate DDL user
```

---

## Running locally

```bash
cp .env.example .env   # fill in required values (see below)
docker compose up --build
docker compose exec backend alembic upgrade head
```

- Frontend: `http://localhost:$FRONTEND_PORT` (default 5173)
- Backend API: `http://localhost:$BACKEND_PORT` (default 8000)
- Swagger docs: `http://localhost:$BACKEND_PORT/docs`

### Minimum required env vars

| Variable | Notes |
|---|---|
| `SECRET_KEY` | `openssl rand -hex 32` |
| `DATABASE_URL` | `postgresql+asyncpg://questboard:pw@postgres/questboard` |
| `DATABASE_MIGRATE_URL` | Same but using the `questboard_migrate` user |
| `OIDC_DISCOVERY_URL` | Provider's `.well-known/openid-configuration` URL |
| `OIDC_CLIENT_ID` | From your OIDC provider |
| `OIDC_CLIENT_SECRET` | From your OIDC provider |
| `OIDC_REDIRECT_URI` | `http://localhost:8000/auth/callback` in dev |
| `APP_URL` | Frontend origin — `http://localhost:5173` in dev |

---

## Database conventions

- **Two DB users**: `questboard` (app, DML only) and `questboard_migrate`
  (Alembic, DDL). Never use the migrate user from application code.
- **All PKs are UUIDs** (`UUID(as_uuid=True)`) — prevents enumeration attacks.
- **Never edit an existing migration.** Always generate a new one:
  ```bash
  docker compose exec backend alembic revision --autogenerate -m "describe change"
  docker compose exec backend alembic upgrade head
  ```
- **Import every new model** in `backend/app/models/__init__.py` so Alembic's
  autogenerate picks it up.
- The migrate URL uses `postgresql+asyncpg://` but Alembic `env.py` strips the
  `+asyncpg` driver prefix for synchronous use.

### Current migration chain (in order)

1. `e3a8f2c1d9b4` — initial schema
2. `b3c4d5e6f7a8` — v1 completion and v2 groundwork
3. `c5d6e7f8a9b0` — vote notifications and autocomplete
4. `d6e7f8a9b0c1` — session notes per-visibility
5. `e7f8a9b0c1d2` — milestones
6. `f8a9b0c1d2e3` — bot campaign fields
7. `930af97f5798` — lore entries
8. `98520cae8a4b` — character sheets and recap email

---

## Data model overview

| Model | Table | Notes |
|---|---|---|
| `User` | `users` | Unique on `(oidc_sub, oidc_issuer)`. Has `display_name_override`, `timezone`, `is_admin`, `recap_email_opt_in`. |
| `Campaign` | `campaigns` | Has `guild_id`, `notification_channel_id` for bot routing; `reminder_offsets_minutes` JSONB. |
| `CampaignMember` | `campaign_members` | PK is `(campaign_id, user_id)`. Roles: `gm`, `player`. Has `character_sheet_url`. |
| `Session` | `sessions` | `SchedulingMode`: vote/direct/tentative. `SessionStatus`: proposed/confirmed/completed/cancelled. Has `summary`, `transcript`, `recording_url`. |
| `TimeSlot` | `time_slots` | Proposed times for vote-mode sessions. |
| `Vote` | `votes` | `Availability`: yes/maybe/no. Unique on `(time_slot_id, user_id)`. |
| `SessionNote` | `session_notes` | Per-user notes. `NoteVisibility`: private/public. Unique on `(session_id, user_id, visibility)`. |
| `SessionAttendance` | `session_attendance` | PK is `(session_id, user_id)`. `attended` bool, defaults true. |
| `PlatformLink` | `platform_links` | Links a User to a Discord or Matrix account. |
| `Milestone` | `milestones` | Campaign milestones, optionally linked to a session. |
| `LoreEntry` | `lore_entries` | Campaign wiki entries. `LoreType`: location/faction/npc/item/event/other. |
| `AppSetting` | `app_settings` | Key-value store for admin-configurable settings (SMTP, bot key, LLM config, etc.). |

---

## Authentication and authorisation

### User auth (OIDC + session cookie)

- Login flow: `GET /auth/login` → OIDC provider → `GET /auth/callback` →
  session written to Redis → `qb_session` cookie set → redirect to frontend.
- Cookie: `qb_session`, HttpOnly, SameSite=Lax, Secure (in prod).
- Redis key: `session:{token}`, TTL 8h sliding window.
- PKCE state key: `oidc_state:{state}`, TTL 10 min, deleted on first use.
- After callback: redirect to `{APP_URL}/dashboard`.

### Auth dependencies (use these in routers)

```python
get_current_user         # Returns User or raises 401
require_campaign_member  # Returns User or raises 403 (needs campaign_id path param)
require_gm               # Returns User or raises 403 (needs campaign_id path param)
get_session_for_member   # Returns Session or raises 403/404 (needs session_id path param)
get_session_for_gm       # Returns Session or raises 403/404 (needs session_id path param)
require_admin            # Returns User or raises 403
require_bot_auth         # Validates X-Bot-Key header; raises 401 on mismatch
```

### Bot auth

The bot authenticates with `X-Bot-Key: <key>` on all `/api/bot/*` endpoints.
The key is stored in `app_settings` and validated via `secrets.compare_digest`.
Generate/rotate it in the Admin → Bot Settings panel.

---

## API organisation

Routers are mounted in `main.py`:

| Prefix | Router file | Who uses it |
|---|---|---|
| `/auth` | `routers/auth.py` | Browser (OIDC flow) |
| `/api` | `routers/users.py` | Frontend + admin |
| `/api/campaigns` | `routers/campaigns.py` | Frontend |
| `/api` | `routers/sessions.py` | Frontend |
| `/api` | `routers/timeslots.py` | Frontend |
| `/api` | `routers/votes.py` | Frontend |
| `/api` | `routers/bot.py` | Discord bot only (`X-Bot-Key`) |

Route ordering matters inside campaign router: literal paths (`/join`, `/me`)
must be declared **before** parameterised paths (`/{campaign_id}`).

---

## Celery tasks

All tasks live in `backend/app/tasks/reminder_tasks.py`. Key tasks:

| Task name | When fired |
|---|---|
| `send_session_confirmed` | Session confirmed; routes to bot or webhook |
| `send_session_reminder` | Scheduled at reminder offsets before session time |
| `send_session_proposed` | Vote-mode session created on a bot-connected campaign |
| `send_session_cancelled` | Session cancelled on a bot-connected campaign |
| `send_session_completed` | Session auto-transitions confirmed → completed |
| `send_vote_notification` | Each vote cast (mode=each_vote) or all votes in (mode=all_voted) |
| `send_recap_email` | After bot uploads a transcript |
| `auto_close_voting` | Scheduled when vote-mode session created (if vote_auto_close_hours set) |
| `auto_complete_sessions` | Celery Beat, every 5 min; confirmed → completed when time passes |

### Bot notification routing pattern

Every task that sends a notification follows this pattern:

1. If `guild_id` and `bot_url` are both set → POST to `{bot_url}/notify` with
   `X-Bot-Key`. On success, return early. On HTTP failure, log a warning and
   **fall through** to the webhook (do not silently drop).
2. Otherwise → post to the Discord webhook directly.

---

## Adding a new feature — checklist

1. **Model** — add a file in `backend/app/models/`, import it in `models/__init__.py`.
2. **Migration** — `alembic revision --autogenerate -m "..."`, then `alembic upgrade head`.
3. **Schema** — add Pydantic request/response models in `backend/app/schemas/`.
4. **Service** — add business logic in `backend/app/services/`. Keep DB access out of routers.
5. **Router** — add endpoints in `backend/app/routers/`. Register in `main.py` if it's a new file.
6. **Frontend API client** — add fetch functions in `frontend/src/api/`.
7. **Frontend page/component** — add in `frontend/src/pages/` or `components/`. Register route in `App.jsx`.

---

## Important constraints

- **No local passwords.** Auth is OIDC-only; never store or accept passwords.
- **No TLS in this codebase.** It's terminated by the external reverse proxy.
- **All UUIDs, no integer PKs.**
- **`votes.updated_at` has `server_default` only** — the service layer must set
  it manually on UPDATE.
- **`session.status` server_default** uses `text("'proposed'")` (quoted, for
  PostgreSQL ENUM).
- **`celery_task_ids`** on Session is a JSONB list of Celery task ID strings.
  Set on confirmation so reminders can be revoked on reschedule/cancel.
- **Settings singleton** — import `from app.config import settings`. Never
  instantiate `Settings()` directly.
- **Admin-configurable secrets** (SMTP password, bot API key, LLM API key) are
  stored in `app_settings` via `settings_service`, not in env vars, so they can
  be rotated without a redeploy.
