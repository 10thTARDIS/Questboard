"""OIDC authentication routes: /auth/login, /auth/callback, /auth/logout."""

import hmac
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, Cookie, Depends, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.oidc import (
    build_authorization_url,
    exchange_code_for_tokens,
    fetch_oidc_discovery,
    fetch_userinfo,
    generate_pkce_pair,
    generate_state,
)
from app.auth.session import (
    consume_pkce_state,
    create_session,
    delete_session,
    store_pkce_state,
)
from app.config import settings
from app.database import get_db
from app.limiter import limiter
from app.models.user import User

router = APIRouter()

_COOKIE_NAME = "qb_session"
_COOKIE_OPTS: dict = {
    "httponly": True,
    "samesite": "lax",
    "secure": True,
}


def _error_redirect(message: str) -> RedirectResponse:
    """Redirect the browser to the frontend error page with a human-readable message."""
    return RedirectResponse(
        url=f"{settings.app_url}/auth-error?message={quote(message)}",
        status_code=302,
    )


@router.get("/login", include_in_schema=True)
@limiter.limit("10/minute")
async def login(
    request: Request,
    invite_code: str | None = Query(default=None, description="Required if INVITE_CODE is set"),
) -> RedirectResponse:
    """Initiate the OIDC authorization flow with PKCE.

    Stores (state → code_verifier + invite_code) in Redis for 10 minutes,
    then redirects the browser to the provider's authorization endpoint.
    """
    try:
        discovery = await fetch_oidc_discovery()
    except Exception:
        return _error_redirect(
            "Could not reach the identity provider. "
            "Check OIDC_DISCOVERY_URL and try again."
        )

    code_verifier, code_challenge = generate_pkce_pair()
    state = generate_state()

    await store_pkce_state(state, code_verifier, invite_code or "")
    auth_url = build_authorization_url(discovery, state, code_challenge)
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/callback", include_in_schema=True)
@limiter.limit("10/minute")
async def callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle the OIDC provider redirect after the user authenticates.

    Validates CSRF state, exchanges the code for tokens (PKCE), fetches
    the user profile, upserts the User record, creates a Redis session,
    and sets the session cookie.
    """
    # ── 1. Validate & consume state (CSRF + replay protection) ────────────────
    pkce_data = await consume_pkce_state(state)
    if pkce_data is None:
        return _error_redirect(
            "The sign-in request expired or was already used. Please try again."
        )

    code_verifier: str = pkce_data["code_verifier"]
    invite_code: str = pkce_data.get("invite_code", "")

    # ── 2. Exchange code for tokens ────────────────────────────────────────────
    discovery = await fetch_oidc_discovery()
    try:
        tokens = await exchange_code_for_tokens(discovery, code, code_verifier)
    except Exception:
        return _error_redirect(
            "Failed to exchange the authorization code with your identity provider. "
            "Please try signing in again."
        )

    # ── 3. Fetch user profile from provider ───────────────────────────────────
    try:
        userinfo = await fetch_userinfo(discovery, tokens["access_token"])
    except Exception:
        return _error_redirect(
            "Signed in successfully but could not retrieve your profile. "
            "Please try again."
        )

    sub: str = userinfo["sub"]
    issuer: str = discovery["issuer"]

    # ── 4. Upsert user record ──────────────────────────────────────────────────
    try:
        result = await db.execute(
            select(User).where(User.oidc_sub == sub, User.oidc_issuer == issuer)
        )
        user = result.scalar_one_or_none()

        if user is None:
            # New user — check invite code gate
            if settings.invite_code and not hmac.compare_digest(invite_code, settings.invite_code):
                return _error_redirect(
                    "A valid invite code is required to register. "
                    "Please ask your GM for an invite code and try again."
                )
            # First user ever becomes admin automatically
            from sqlalchemy import func
            user_count = await db.scalar(select(func.count()).select_from(User)) or 0
            user = User(
                id=uuid.uuid4(),
                oidc_sub=sub,
                oidc_issuer=issuer,
                display_name=(
                    userinfo.get("name")
                    or userinfo.get("preferred_username")
                    or sub
                ),
                email=userinfo.get("email"),
                avatar_url=userinfo.get("picture"),
                is_admin=(user_count == 0),
                last_login_at=datetime.now(timezone.utc),
            )
            db.add(user)
            await db.flush()
        else:
            # Existing user — refresh profile from provider
            user.display_name = (
                userinfo.get("name")
                or userinfo.get("preferred_username")
                or user.display_name
            )
            if userinfo.get("email"):
                user.email = userinfo["email"]
            if userinfo.get("picture"):
                user.avatar_url = userinfo["picture"]
            user.last_login_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(user)
    except Exception:
        return _error_redirect(
            "A database error occurred while creating your account. "
            "Please contact the administrator."
        )

    # ── 5. Create server-side session and set cookie ───────────────────────────
    session_id = await create_session(str(user.id))

    # Redirect to the frontend dashboard.
    # APP_URL must point to the frontend origin (e.g. https://questboard.example.com
    # in production, or http://localhost:5173 when running the Vite dev server).
    response = RedirectResponse(url=f"{settings.app_url}/dashboard", status_code=302)
    response.set_cookie(
        key=_COOKIE_NAME,
        value=session_id,
        max_age=settings.session_ttl_seconds,
        **_COOKIE_OPTS,
    )
    return response


@router.get("/logout")
@limiter.limit("10/minute")
async def logout(
    request: Request,
    qb_session: str | None = Cookie(default=None, alias=_COOKIE_NAME),
) -> RedirectResponse:
    """Delete the server-side session and clear the cookie."""
    if qb_session:
        await delete_session(qb_session)

    response = RedirectResponse(url=f"{settings.app_url}/login", status_code=302)
    response.delete_cookie(key=_COOKIE_NAME, samesite="lax", secure=True)
    return response
