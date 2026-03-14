# Quest Board

A self-hosted TTRPG session scheduling tool. The GM proposes time slots, players vote, and the group gets reminded via Discord before every session.  This was created due to the apparently-imminent shutdown of RollRota; the SSL certificate for the site has not been renewed after being expired for a month, no new features have been added in a very very long time, and the developers are no longer active in their Discord.

### AI Usage Disclaimer

This project has been created with the assistance of Claude Code, which is an AI coding tool, and may contain errors or vulnerabilities.  Review the code before running it to ensure you are comfortable with the risks.

## Features

- **OIDC authentication** — works with Authentik, Keycloak, Google, or any compliant provider; no passwords stored
- **Three scheduling modes** — vote (2–5 proposed slots), direct (auto-confirmed), tentative (pending GM confirmation)
- **Voting grid** — yes/maybe/no availability, scored and highlighted in real time
- **Discord notifications** — confirmation and 7-day/24-hour/1-hour reminders via webhook
- **Invite-code gating** — optional `INVITE_CODE` env var controls who can register
- **Per-campaign webhooks** — each campaign can have its own Discord channel

---

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) 24+
- [Docker Compose](https://docs.docker.com/compose/) v2 plugin
- An OIDC provider (Authentik, Keycloak, Google, etc.) with a configured application
- (Optional) A Discord webhook URL for notifications

---

## Quick Start (Development)

> **Going straight to production?** The Development and Production sections below are independent — you do not need to run the development stack first.

### 1. Clone and configure

```bash
git clone https://github.com/10thTARDIS/Questboard quest-board
cd quest-board
cp .env.example .env
```

Edit `.env` — the minimum required fields are:

| Variable | Description |
|---|---|
| `SECRET_KEY` | Run `openssl rand -hex 32` |
| `DATABASE_URL` | Must match Postgres credentials below |
| `DATABASE_MIGRATE_URL` | Uses the migrate user (DDL privileges) |
| `OIDC_DISCOVERY_URL` | Provider's `.well-known/openid-configuration` URL |
| `OIDC_CLIENT_ID` | Client ID from your OIDC provider |
| `OIDC_CLIENT_SECRET` | Client secret from your OIDC provider |
| `OIDC_REDIRECT_URI` | Must be `http://localhost:8000/auth/callback` in dev |
| `APP_URL` | Frontend URL — `http://localhost:5173` in dev |

### 2. Start the stack

```bash
docker compose up --build
```

Services (default ports — override in `.env` if needed):
- **Frontend** → http://localhost:`$FRONTEND_PORT` (default 5173)
- **Backend API** → http://localhost:`$BACKEND_PORT` (default 8000)
- **API docs** → http://localhost:`$BACKEND_PORT`/docs

### 3. Run database migrations

On first start (or after pulling new migrations):

```bash
docker compose exec backend alembic upgrade head
```

### 4. Sign in

Navigate to http://localhost:5173 and click **Sign in with SSO**. If `INVITE_CODE` is set in your `.env`, enter it before signing in to register a new account.

---

## Production Deployment

### 1. Clone and configure

```bash
git clone https://github.com/10thTARDIS/Questboard quest-board
cd quest-board
cp .env.example .env
```

Edit `.env` with real secrets and your public domain. Key changes from the development defaults:

- Set `APP_URL` to your public URL (e.g. `https://questboard.example.com`)
- Set `OIDC_REDIRECT_URI` to `https://questboard.example.com/auth/callback`
- Use strong, unique values for `SECRET_KEY`, `POSTGRES_PASSWORD`, and `POSTGRES_MIGRATE_PASSWORD`
- Update `DATABASE_URL` and `DATABASE_MIGRATE_URL` to match

### 2. Start with production overrides

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

This uses the production Docker targets (pre-built assets, no bind mounts, `restart: unless-stopped`).

### 3. Run migrations

```bash
docker compose exec backend alembic upgrade head
```

### 4. Reverse proxy

TLS termination is handled externally. Point your reverse proxy (Caddy, Nginx, Traefik) at the single frontend container port (`HTTP_PORT`, default **80**). The Nginx container in production mode serves the React single-page application (SPA) and automatically proxies all `/api/*` and `/auth/*` traffic to the backend internally — your reverse proxy only needs to talk to one port.

### 5. Done — verify

Navigate to your public URL and sign in. If `INVITE_CODE` is set, the first user must supply it during registration.

---

## Environment Variables

See `.env.example` for the full list with descriptions. Key variables:

| Variable | Required | Default | Description |
|---|---|---|---|
| `BACKEND_PORT` | No | `8000` | **Dev only** — host port for the FastAPI API |
| `FRONTEND_PORT` | No | `5173` | **Dev only** — host port for the Vite dev server |
| `HTTP_PORT` | No | `80` | **Prod only** — host port for the Nginx frontend |
| `APP_URL` | Yes | — | Frontend origin URL (no trailing slash) |
| `SECRET_KEY` | Yes | — | Random hex string; `openssl rand -hex 32` |
| `INVITE_CODE` | No | `""` | If set, required to register new accounts |
| `DATABASE_URL` | Yes | — | `postgresql+asyncpg://user:pass@host/db` |
| `DATABASE_MIGRATE_URL` | Yes | — | `postgresql+asyncpg://migrate_user:pass@host/db` |
| `REDIS_URL` | No | `redis://redis:6379/0` | Redis for sessions and task broker |
| `OIDC_DISCOVERY_URL` | Yes | — | Provider's discovery document URL |
| `OIDC_CLIENT_ID` | Yes | — | OIDC client ID |
| `OIDC_CLIENT_SECRET` | Yes | — | OIDC client secret |
| `OIDC_REDIRECT_URI` | Yes | — | Must match redirect URI in your provider |
| `DEFAULT_DISCORD_WEBHOOK_URL` | No | `""` | Fallback webhook if campaign has none |
| `CELERY_BROKER_URL` | No | `redis://redis:6379/1` | Celery message broker |
| `CELERY_RESULT_BACKEND` | No | `redis://redis:6379/2` | Celery result storage |

---

## OIDC Provider Setup

### Authentik

1. Create a new **OAuth2/OpenID Connect Provider** application
2. Set the redirect URI to `https://questboard.example.com/auth/callback`
3. Copy the **Client ID** and **Client Secret** to `.env`
4. Set `OIDC_DISCOVERY_URL` to `https://auth.example.com/application/o/<slug>/.well-known/openid-configuration`

### Other providers

Any compliant OIDC provider works. Use the provider's `.well-known/openid-configuration` URL and set `openid profile email` scopes.

---

## Discord Notifications

1. In your Discord server, go to **Channel Settings → Integrations → Webhooks**
2. Create a new webhook and copy the URL
3. Set it as `DEFAULT_DISCORD_WEBHOOK_URL` in `.env` for a global fallback, or paste it into a campaign's settings for per-campaign routing

Reminders are sent at:
- Session confirmed → immediate notification
- 7 days before the session
- 24 hours before the session
- 1 hour before the session

---

## Updating

### Development

```bash
# 1. Pull the latest code
git pull

# 2. Rebuild images to pick up any dependency changes
docker compose up --build -d

# 3. Apply any new database migrations
docker compose exec backend alembic upgrade head
```

### Production

```bash
# 1. Pull the latest code
git pull

# 2. Rebuild and restart all services with the new images
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d

# 3. Apply any new database migrations
docker compose exec backend alembic upgrade head
```

> **Note:** `alembic upgrade head` is safe to run even when there are no new migrations — it will report "Already at head" and exit cleanly. Running it after every update is a good habit.

> **Note:** Active user sessions are stored in Redis and survive container restarts. Users will not be logged out by an update unless Redis data is cleared.

---

## Development Notes

### Backend

```bash
# Install dev dependencies
pip install -r backend/requirements-dev.txt

# Run linter
ruff check backend/

# Run formatter
black backend/

# Generate a new migration after model changes
docker compose exec backend alembic revision --autogenerate -m "describe change"

# Apply migrations
docker compose exec backend alembic upgrade head
```

### Frontend

```bash
cd frontend
npm install
npm run dev      # Vite dev server on :5173
npm run build    # Production build
```

---

## Security Hardening

- All secrets are environment variables — never committed to source control
- OIDC with PKCE — no passwords stored anywhere in this application
- Sessions stored server-side in Redis; cookies contain only an opaque ID (`HttpOnly`, `SameSite=Lax`, `Secure`)
- Auth endpoints rate-limited to 10 requests/minute per IP (slowapi)
- Security headers on every response: `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Content-Security-Policy`
- App database user has DML-only privileges; Alembic uses a separate DDL-privileged user
- All containers run as non-root users

---

## Dependency Auditing

Run `pip-audit` to check for known vulnerabilities in Python dependencies:

```bash
pip install pip-audit
pip-audit -r backend/requirements.txt
```

To run automatically before every commit, install [pre-commit](https://pre-commit.com/) and the hooks:

```bash
pip install pre-commit
pre-commit install
```

The `.pre-commit-config.yaml` in the repo root runs `pip-audit` on every commit.
