"""API key authentication middleware."""
from typing import Optional

from fastapi import Header, HTTPException, status


def verify_api_key(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")
) -> str:
    """Validate API key from X-API-Key header.

    Args:
        x_api_key: API key from request header.

    Returns:
        The validated API key.

    Raises:
        HTTPException: If key is missing or invalid.
    """
    valid_key = "elevator-secret-key-123"  # TODO: load from Settings

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
