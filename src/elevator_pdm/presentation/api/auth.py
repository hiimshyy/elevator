"""API key authentication middleware."""
from functools import lru_cache

from fastapi import Header, HTTPException, status

from elevator_pdm.infrastructure.config.settings import Settings


@lru_cache
def get_settings() -> Settings:
    """Load and cache application settings for auth checks."""
    return Settings()


def verify_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key")
) -> str:
    """Validate API key from X-API-Key header.

    Args:
        x_api_key: API key from request header.

    Returns:
        The validated API key.

    Raises:
        HTTPException: If key is missing or invalid.
    """
    valid_key = get_settings().api.key

    if x_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    if x_api_key != valid_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return x_api_key
