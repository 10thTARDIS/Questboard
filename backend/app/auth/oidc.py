"""OIDC discovery, PKCE pair generation, and token/userinfo exchange."""

import secrets
import time
from urllib.parse import urlencode

import httpx
from authlib.common.security import generate_token
from authlib.oauth2.rfc7636 import create_s256_code_challenge

from app.config import settings

# ── Discovery document cache (TTL: 1 hour) ────────────────────────────────────
_discovery_cache: dict | None = None
_discovery_cache_ts: float = 0.0
_DISCOVERY_CACHE_TTL = 3600


async def fetch_oidc_discovery() -> dict:
    """Fetch (and cache) the provider's OIDC discovery document."""
    global _discovery_cache, _discovery_cache_ts
    now = time.monotonic()
    if _discovery_cache and (now - _discovery_cache_ts) < _DISCOVERY_CACHE_TTL:
        return _discovery_cache
    async with httpx.AsyncClient() as client:
        response = await client.get(settings.oidc_discovery_url, timeout=10)
        response.raise_for_status()
        _discovery_cache = response.json()
        _discovery_cache_ts = now
    return _discovery_cache


# ── PKCE ──────────────────────────────────────────────────────────────────────

def generate_pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge_S256)."""
    code_verifier: str = generate_token(128)
    code_challenge: str = create_s256_code_challenge(code_verifier)
    return code_verifier, code_challenge


def generate_state() -> str:
    """Return a cryptographically random CSRF state token (256 bits)."""
    return secrets.token_urlsafe(32)


# ── Authorization URL ─────────────────────────────────────────────────────────

def build_authorization_url(
    discovery: dict,
    state: str,
    code_challenge: str,
) -> str:
    """Build the full authorization URL to redirect the browser to.

    Requests the `openid profile email` scopes and uses S256 PKCE so the
    authorization code cannot be replayed even if intercepted in transit.
    """
    params = {
        "response_type": "code",
        "client_id": settings.oidc_client_id,
        "redirect_uri": settings.oidc_redirect_uri,
        "scope": "openid profile email",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{discovery['authorization_endpoint']}?{urlencode(params)}"


# ── Token exchange ────────────────────────────────────────────────────────────

async def exchange_code_for_tokens(
    discovery: dict,
    code: str,
    code_verifier: str,
) -> dict:
    """Exchange an authorization code + PKCE verifier for access/ID tokens."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            discovery["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.oidc_redirect_uri,
                "client_id": settings.oidc_client_id,
                "client_secret": settings.oidc_client_secret,
                "code_verifier": code_verifier,
            },
            headers={"Accept": "application/json"},
            timeout=15,
        )
        response.raise_for_status()
        return response.json()


# ── Userinfo ──────────────────────────────────────────────────────────────────

async def fetch_userinfo(discovery: dict, access_token: str) -> dict:
    """Fetch the authenticated user's profile from the userinfo endpoint."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            discovery["userinfo_endpoint"],
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
