"""
FastAPI application entry point.

AI Hotel Booking Agent.

Phase 9 features:

- Rate limiting
- CORS configuration
- Redis/shared storage
- Admin API
- Voice API
- Telephony API
"""

from fastapi import FastAPI

from fastapi.middleware.cors import (
    CORSMiddleware,
)

from sqlalchemy import text

from slowapi.errors import (
    RateLimitExceeded,
)

from slowapi.middleware import (
    SlowAPIMiddleware,
)

from slowapi import (
    _rate_limit_exceeded_handler,
)

from app.config import settings

from app.database.db import engine

from app.rate_limit import limiter

from app.api import (
    rooms,
    bookings,
    chat,
    voice,
    telephony,
    admin,
)


# ============================================================
# FastAPI Application
# ============================================================

app = FastAPI(
    title="AI Hotel Booking Agent",
    description=(
        "Backend API for the AI Voice Hotel "
        "Booking Agent project."
    ),
    version="0.1.0",
)


# ============================================================
# Phase 9.4 - Rate Limiting
# ============================================================

app.state.limiter = limiter

app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
)

app.add_middleware(
    SlowAPIMiddleware,
)


# ============================================================
# CORS
# ============================================================

_cors_origins = [
    origin.strip()
    for origin in settings.CORS_ORIGINS.split(",")
    if origin.strip()
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


# ============================================================
# Routers
# ============================================================

app.include_router(
    rooms.router,
)

app.include_router(
    bookings.router,
)

app.include_router(
    chat.router,
)

app.include_router(
    voice.router,
)

app.include_router(
    telephony.router,
)

app.include_router(
    admin.router,
)


# ============================================================
# Root
# ============================================================

@app.get("/")
def root():
    """
    Simple liveness check.
    """

    return {
        "status": "ok",
        "message": (
            "AI Hotel Booking Agent "
            "backend is running"
        ),
    }


# ============================================================
# Database Health
# ============================================================

@app.get("/health/db")
def health_db():
    """
    Check whether the backend can communicate with MySQL.
    """

    try:

        with engine.connect() as connection:

            connection.execute(
                text("SELECT 1")
            )

        return {
            "status": "ok",
            "database": "connected",
        }

    except Exception as e:

        return {
            "status": "error",
            "database": "not connected",
            "detail": str(e),
        }