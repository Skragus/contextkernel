"""API key verification for kernel endpoints."""

from fastapi import Depends, HTTPException, Header

from app.config import settings


async def verify_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None),
) -> str:
    """Validate API key via X-API-Key or Authorization: Bearer.

    If KERNEL_API_KEY is not set, passes through (no auth).
    If set, requires matching key or raises 401.
    """
    if settings.kernel_api_key is None:
        return ""

    key = x_api_key
    if key is None and authorization and authorization.startswith("Bearer "):
        key = authorization[7:].strip()

    if key != settings.kernel_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    return key
