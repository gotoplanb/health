from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyHeader

from app.auth.api_key import is_valid_api_key
from app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_google_session(request: Request) -> dict:
    """Dependency: require a valid Google OAuth session for browser routes."""
    if settings.mock_auth:
        return {"email": "dev@example.com", "name": "Dev User"}

    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


async def require_api_key(key: str = Depends(api_key_header)) -> str:
    """Dependency: require a valid API key for programmatic routes."""
    if not key or not is_valid_api_key(key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return key
