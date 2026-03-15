"""Server-side session management via Redis.

Sessions are stored as opaque IDs in an HttpOnly cookie.  The Redis key
holds the user_id (and potentially other session metadata) as JSON.

PKCE state tokens (state → code_verifier) are also managed here because
they share the same Redis connection and follow the same pattern.
"""

import json
import secrets

import redis.asyncio as aioredis

from app.config import settings

_SESSION_PREFIX = "session:"
_STATE_PREFIX = "oidc_state:"
_PKCE_TTL = 600  # 10 minutes — OIDC state tokens expire quickly


def _redis() -> aioredis.Redis:
    """Return an async Redis client.  Use as an async context manager."""
    return aioredis.from_url(settings.redis_url, decode_responses=True)


# ── User sessions ─────────────────────────────────────────────────────────────

async def create_session(user_id: str) -> str:
    """Create a new session for user_id.  Returns the opaque session token."""
    session_id = secrets.token_urlsafe(32)
    payload = json.dumps({"user_id": user_id})
    async with _redis() as r:
        await r.setex(f"{_SESSION_PREFIX}{session_id}", settings.session_ttl_seconds, payload)
    return session_id


async def get_session(session_id: str) -> str | None:
    """Return the user_id for a valid session, or None if missing/expired.

    Refreshes the TTL on each successful lookup (sliding expiry).
    """
    key = f"{_SESSION_PREFIX}{session_id}"
    async with _redis() as r:
        payload = await r.get(key)
        if payload is None:
            return None
        # Sliding window — extend TTL on activity
        await r.expire(key, settings.session_ttl_seconds)
        return json.loads(payload)["user_id"]


async def delete_session(session_id: str) -> None:
    async with _redis() as r:
        await r.delete(f"{_SESSION_PREFIX}{session_id}")


# ── OIDC PKCE state ───────────────────────────────────────────────────────────

async def store_pkce_state(
    state: str,
    code_verifier: str,
    invite_code: str = "",
) -> None:
    """Store PKCE (state → code_verifier + invite_code) with a 10-minute TTL."""
    payload = json.dumps({"code_verifier": code_verifier, "invite_code": invite_code})
    async with _redis() as r:
        await r.setex(f"{_STATE_PREFIX}{state}", _PKCE_TTL, payload)


async def consume_pkce_state(state: str) -> dict | None:
    """Retrieve and atomically delete the PKCE state token.

    Returns None if the token is missing or expired.  Deleting before use
    prevents replay attacks — a second callback with the same state will fail.
    """
    key = f"{_STATE_PREFIX}{state}"
    async with _redis() as r:
        payload = await r.getdel(key)
    if payload is None:
        return None
    return json.loads(payload)


# ── Discord account linking tokens ────────────────────────────────────────────

_DISCORD_LINK_PREFIX = "discord_link:"
_DISCORD_LINK_DONE_PREFIX = "discord_link_done:"
_DISCORD_LINK_TTL = 600       # 10 minutes — set by bot, consumed by /auth/link
_DISCORD_LINK_DONE_TTL = 900  # 15 minutes — set by /auth/link, consumed by bot poll


async def store_discord_link_token(token: str, discord_user_id: str) -> None:
    """Store a one-time linking token (called by the bot via POST /api/bot/linking-tokens)."""
    async with _redis() as r:
        await r.setex(f"{_DISCORD_LINK_PREFIX}{token}", _DISCORD_LINK_TTL, discord_user_id)


async def consume_discord_link_token(token: str) -> str | None:
    """Atomically read and delete the token. Returns discord_user_id or None if expired/missing."""
    async with _redis() as r:
        return await r.getdel(f"{_DISCORD_LINK_PREFIX}{token}")


async def store_discord_link_done(token: str, user_id: str) -> None:
    """Store the completion record so the bot can poll for success."""
    async with _redis() as r:
        await r.setex(f"{_DISCORD_LINK_DONE_PREFIX}{token}", _DISCORD_LINK_DONE_TTL, user_id)


async def consume_discord_link_done(token: str) -> str | None:
    """Atomically read and delete the completion record. Returns user_id str or None."""
    async with _redis() as r:
        return await r.getdel(f"{_DISCORD_LINK_DONE_PREFIX}{token}")
