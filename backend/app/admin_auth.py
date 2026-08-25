from fastapi import Header, HTTPException
from app.config import settings


def require_admin(
    authorization: str | None = Header(default=None),
):
    if not settings.ADMIN_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Admin authentication is not configured",
        )

    expected = f"Bearer {settings.ADMIN_TOKEN}"

    if authorization != expected:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing admin credentials",
        )

    return True