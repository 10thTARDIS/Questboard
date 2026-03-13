# Quest Board — Architecture

This document describes the system architecture, data model, and key design decisions for the Quest Board TTRPG session scheduling tool.

---

## Table of Contents

1. [High-Level Overview](#high-level-overview)
2. [Service Map](#service-map)
3. [Request Lifecycle](#request-lifecycle)
4. [Authentication Flow](#authentication-flow)
5. [Data Model](#data-model)
6. [Session Scheduling Modes](#session-scheduling-modes)
7. [Notification System](#notification-system)
8. [Security Design](#security-design)
9. [Key Design Decisions](#key-design-decisions)

---

## High-Level Overview

Quest Board is a self-hosted web application with a clean separation between a Python backend API and a React single-page application (SPA) frontend. All services are containerised with Docker Compose.

```
Browser
  │
  ▼
Nginx (port 80/443)
  ├── /api/*  ──────────► FastAPI backend (port 8000)
  ├── /auth/* ──────────► FastAPI backend (port 8000)
  └── /*      ──────────► React SPA (static files)
                                │
                          PostgreSQL (port 5432)
                          Redis (port 6379)
                                │
                         Celery Worker
                         Celery Beat
```

---

## Service Map

| Service | Image / Build | Purpose |
|---------|--------------|---------|
| `db` | `postgres:16-alpine` | Primary data store |
| `redis` | `redis:7-alpine` | Session store, Celery broker & result backend |
| `backend` | `./backend` (Python 3.12) | FastAPI REST API |
| `worker` | `./backend` (same image) | Celery task executor |
| `beat` | `./backend` (same image) | Celery ETA scheduler |
| `frontend` | `./frontend` (Node + Nginx) | Vite dev server (dev) / Nginx SPA (prod) |

### Redis Database Allocation

| Redis DB | Usage |
|----------|-------|
| `0` | User sessions and OIDC PKCE state tokens |
| `1` | Celery broker (task queue) |
| `2` | Celery result backend |

---

## Request Lifecycle

### Typical API request

```
Browser
  │  Cookie: qb_session=<opaque_token>
  ▼
Nginx
  │  proxy_pass http://backend:8000
  ▼
SecurityHeadersMiddleware   ← adds X-Frame-Options, CSP, etc.
  ▼
CORSMiddleware              ← validates Origin against APP_URL
  ▼
Route handler
  │
  ├── get_current_user dependency
  │     ├── Read qb_session cookie
  │     ├── Redis GET session:<token> → user_id
  │     └── PostgreSQL SELECT users WHERE id = user_id
  │
  ├── Authorization dependency (require_campaign_member / require_gm)
  │     └── PostgreSQL SELECT campaign_members WHERE ...
  │
  └── Business logic (service layer)
        └── PostgreSQL (via SQLAlchemy async)
```

### Dependency chain

FastAPI's `Depends()` system wires the chain declaratively. The key dependencies are:

- `get_current_user` — reads the cookie → Redis → database; raises 401 if any step fails
- `require_campaign_member(campaign_id)` — checks the user is a member of the campaign
- `require_gm(campaign_id)` — checks the user holds the GM role
- `get_session_for_member(session_id)` — resolves the campaign from the session, then checks membership
- `get_session_for_gm(session_id)` — same, but requires the GM role

---

## Authentication Flow

Quest Board uses OpenID Connect (OIDC) with PKCE for authentication. No passwords are stored.

```
1. User clicks "Sign in with SSO"
   └── Browser navigates to GET /auth/login

2. /auth/login
   ├── Generates code_verifier + code_challenge (PKCE S256)
   ├── Generates random state token (CSRF protection)
   ├── Stores {code_verifier, invite_code} in Redis with 10-minute TTL
   │     Key: oidc_state:<state>
   └── Redirects browser to provider's authorization_endpoint

3. User authenticates with OIDC provider

4. Provider redirects to GET /auth/callback?code=...&state=...

5. /auth/callback
   ├── Validates & atomically consumes PKCE state from Redis (GETDEL)
   ├── Exchanges authorization code + code_verifier for tokens
   ├── Fetches user profile from provider's userinfo_endpoint
   ├── Upserts User record in PostgreSQL (keyed on oidc_issuer + oidc_sub)
   ├── Checks invite code gate (if INVITE_CODE is set)
   ├── Creates server-side session in Redis (opaque token, 8-hour TTL)
   └── Sets HttpOnly Secure SameSite=Lax cookie: qb_session=<token>

6. Browser is redirected to /dashboard
   └── All subsequent requests send the session cookie automatically
```

### Why server-side sessions?

JWT tokens store all claims in the token itself — revoking them before expiry requires a denylist. Server-side sessions in Redis allow instant logout by simply deleting the key. The cookie is opaque (no information leaks) and the session data lives only on the server.

---

## Data Model

```
users
  ├── id (UUID PK)
  ├── oidc_sub (TEXT)
  ├── oidc_issuer (TEXT)    ← unique together with oidc_sub
  ├── display_name (TEXT)
  ├── email (TEXT nullable)
  └── avatar_url (TEXT nullable)

campaigns
  ├── id (UUID PK)
  ├── name (TEXT)
  ├── game_system (TEXT nullable)
  ├── description (TEXT nullable)
  ├── discord_webhook_url (TEXT nullable)  ← validated to discord.com/api/webhooks/
  ├── invite_code (TEXT unique nullable)
  └── created_at (TIMESTAMPTZ)

campaign_members                            ← join table, PK is (campaign_id, user_id)
  ├── campaign_id (UUID FK → campaigns)
  ├── user_id (UUID FK → users)
  ├── role (ENUM: gm | player)
  └── joined_at (TIMESTAMPTZ)

sessions
  ├── id (UUID PK)
  ├── campaign_id (UUID FK → campaigns)
  ├── title (TEXT nullable)
  ├── description (TEXT nullable)
  ├── scheduling_mode (ENUM: vote | direct | tentative)
  ├── status (ENUM: proposed | confirmed | completed | cancelled)
  ├── confirmed_time (TIMESTAMPTZ nullable)
  ├── session_notes (TEXT nullable)
  ├── created_by (UUID FK → users)
  ├── celery_task_ids (JSONB nullable)      ← IDs of pending reminder tasks
  └── created_at (TIMESTAMPTZ)

time_slots
  ├── id (UUID PK)
  ├── session_id (UUID FK → sessions)
  ├── proposed_time (TIMESTAMPTZ)
  └── created_at (TIMESTAMPTZ)

votes                                       ← one vote per (time_slot, user) pair
  ├── id (UUID PK)
  ├── time_slot_id (UUID FK → time_slots)
  ├── user_id (UUID FK → users)
  ├── availability (ENUM: yes | maybe | no)
  └── updated_at (TIMESTAMPTZ)
```

All foreign keys use `ON DELETE CASCADE` so deleting a campaign removes all its sessions, time slots, votes, and members.

---

## Session Scheduling Modes

### `vote`

- GM creates a session with 2–5 proposed time slots.
- Players visit the session page and click cells in the VotingGrid to indicate availability (yes/maybe/no).
- Scores are calculated client-side: yes=+2, maybe=+1, no=0.
- The highest-scoring slot is highlighted. The GM selects the winner to confirm.

### `direct`

- GM provides exactly one time. The session is immediately created with `status=confirmed`.
- Reminder notifications are scheduled at creation time.

### `tentative`

- GM provides exactly one time. The session is `proposed` until the GM explicitly confirms it.
- Useful when a time is likely but not yet finalised.

---

## Notification System

Notifications are delivered to Discord via webhooks. The system is designed to be pluggable — any class implementing the `NotificationBackend` protocol can be substituted.

### Flow

```
session confirmed
       │
       ▼
session_service._schedule_reminders()
  ├── send_session_confirmed.delay()          ← immediate Celery task
  └── send_session_reminder.apply_async(eta=) ← one task each at -7d, -24h, -1h
         │
         ▼
    Celery worker
         │
         ▼
    DiscordNotificationBackend._post()
         │
         ▼
    Discord webhook HTTP POST
```

### Rescheduling / cancellation

When a session is confirmed a second time (e.g., the GM changes the slot) or cancelled, `_revoke_reminders()` calls `celery_app.control.revoke(task_id, terminate=True)` for each stored task ID before scheduling new ones.

### Webhook priority

1. Campaign-level `discord_webhook_url` (set by the GM in campaign settings)
2. Global `DEFAULT_DISCORD_WEBHOOK_URL` environment variable
3. No notification sent if neither is set

---

## Security Design

| Concern | Mechanism |
|---------|-----------|
| Authentication | OIDC PKCE — no passwords stored |
| Session management | Server-side Redis sessions, opaque cookie |
| CSRF | SameSite=Lax cookie + state parameter in OIDC flow |
| PKCE replay | Atomic `GETDEL` — state token consumed in a single Redis command |
| Authorisation | FastAPI dependency chain checks campaign membership / GM role per request |
| Invite code comparison | `hmac.compare_digest` — constant-time, prevents timing attacks |
| SSRF | `discord_webhook_url` validated to start with `https://discord.com/api/webhooks/` |
| Rate limiting | slowapi: 10 req/min on all `/auth/*` endpoints, keyed by remote IP |
| Security headers (API) | `SecurityHeadersMiddleware`: X-Frame-Options, X-Content-Type-Options, Referrer-Policy, CSP |
| Security headers (SPA) | Nginx `add_header` directives in `nginx.conf` |
| Secrets leakage | Global exception handler returns only `{"detail": "Internal server error"}` |
| SQL injection | SQLAlchemy ORM with parameterised queries — no raw SQL in application code |
| Dependency vulnerabilities | `pip-audit` in pre-commit hooks |

---

## Key Design Decisions

### Why async SQLAlchemy?

FastAPI is built on Starlette/asyncio. Using `asyncpg` + async SQLAlchemy means database I/O does not block the event loop, allowing the single worker process to handle concurrent requests efficiently.

### Why Celery for reminders?

Reminders need to fire at precise times in the future (up to 7 days ahead). Celery's ETA mechanism (`apply_async(eta=...)`) combined with the beat scheduler handles this reliably without requiring a polling loop in the application server.

### Why pass all data as Celery task arguments?

Celery tasks run in separate worker processes that don't share memory with the web server. The simplest and most robust approach is to pass everything the task needs (campaign name, session title, webhook URL, etc.) as arguments at schedule time. This avoids the complexity of async database access inside synchronous Celery tasks.

### Why Redis for sessions instead of database-stored JWTs?

- **Instant revocation**: deleting a Redis key logs the user out immediately with no denylist needed.
- **Low latency**: Redis key lookups are sub-millisecond; a database query for every request would add unnecessary load.
- **Simplicity**: no JWT library, no key rotation, no claim validation logic.

### Why a NotificationBackend Protocol?

The `runtime_checkable` Protocol allows the Discord backend to be swapped for another implementation (email, Slack, etc.) by assigning a different object to the `discord_backend` module variable — or by dependency injection in tests — without changing any service or task code.
