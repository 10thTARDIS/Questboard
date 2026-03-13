"""FastAPI application factory and global configuration for Quest Board.

Startup order matters:
  1. Rate-limiting exception handler is registered first.
  2. Middleware is applied in reverse registration order (outermost first):
       request → SecurityHeaders → CORS → route handler → CORS → SecurityHeaders → response
     This means SecurityHeaders runs on both inbound and outbound paths,
     ensuring headers are always present even when CORS rejects the request.
  3. Routers are mounted with their URL prefixes.
  4. A catch-all exception handler prevents internal stack traces leaking to clients.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.limiter import limiter
from app.middleware.security import SecurityHeadersMiddleware
from app.routers import auth, campaigns, sessions, timeslots, users, votes

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Quest Board",
    description="Self-hosted TTRPG session scheduling tool.",
    version="0.1.0",
)

# ── Rate limiting ───────────────────────────────────────────────────────────────
# Attach the limiter to app.state so slowapi's @limiter.limit decorator can find it.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Middleware (outermost first) ────────────────────────────────────────────────
# FastAPI/Starlette applies middleware in reverse registration order, so the last
# add_middleware() call here becomes the outermost (first to see requests).
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    # Restrict to the exact frontend origin — wildcards would bypass cookie security.
    allow_origins=[settings.app_url],
    allow_credentials=True,  # Required for the qb_session cookie to be sent cross-origin
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(users.router, prefix="/api", tags=["users"])
app.include_router(campaigns.router, prefix="/api/campaigns", tags=["campaigns"])
app.include_router(sessions.router, prefix="/api", tags=["sessions"])
app.include_router(timeslots.router, prefix="/api", tags=["timeslots"])
app.include_router(votes.router, prefix="/api", tags=["votes"])


# ── Global exception handler ───────────────────────────────────────────────────
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ── Health check ───────────────────────────────────────────────────────────────
@app.get("/health", tags=["health"])
async def health_check() -> dict:
    return {"status": "ok"}
