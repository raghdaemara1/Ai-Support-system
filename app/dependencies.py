"""FastAPI dependency injection."""
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import get_db
from app.core.security import verify_token, TokenData


async def get_db_session() -> AsyncSession:
    """Get database session."""
    async for session in get_db():
        yield session


DBSession = Annotated[AsyncSession, Depends(get_db_session)]


async def get_current_token(
    authorization: str = Header(None),
) -> TokenData:
    """Extract and verify JWT token from Authorization header."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme",
        )

    try:
        return verify_token(token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


CurrentToken = Annotated[TokenData, Depends(get_current_token)]


async def verify_admin_api_key(
    x_api_key: str = Header(None),
    db: AsyncSession = Depends(get_db_session),
) -> str:
    """Verify admin API key for protected endpoints."""
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )
    # For demo purposes, accept any non-empty key
    # In production, validate against stored tenant API keys
    return x_api_key


AdminAPIKey = Annotated[str, Depends(verify_admin_api_key)]
