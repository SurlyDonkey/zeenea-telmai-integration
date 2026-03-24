"""
API key authentication dependency.
If INTEGRATION_API_KEY env var is not set, the API is open (dev mode).
"""
import os

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)) -> None:
    expected = os.getenv("INTEGRATION_API_KEY", "")
    if not expected:
        # No key configured — open access for local / dev environments
        return
    if api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )
