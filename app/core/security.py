"""Security utilities for authentication and authorization."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import settings
from app.core.exceptions import AuthenticationError


class TokenData(BaseModel):
    """JWT token payload."""
    tenant_id: str
    customer_id: str | None = None
    exp: datetime


def create_access_token(
    tenant_id: str,
    customer_id: str | None = None,
    expires_delta: timedelta = timedelta(hours=24),
) -> str:
    """Create a JWT access token."""
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {
        "tenant_id": tenant_id,
        "customer_id": customer_id,
        "exp": expire,
    }
    return jwt.encode(to_encode, settings.app_secret_key, algorithm="HS256")


def verify_token(token: str, tenant_id: str | None = None) -> TokenData:
    """Verify JWT token and optionally check tenant_id matches."""
    try:
        payload = jwt.decode(token, settings.app_secret_key, algorithms=["HS256"])
        token_data = TokenData(
            tenant_id=payload["tenant_id"],
            customer_id=payload.get("customer_id"),
            exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        )

        if tenant_id and token_data.tenant_id != tenant_id:
            raise AuthenticationError("Token tenant mismatch")

        return token_data

    except JWTError as e:
        raise AuthenticationError(f"Invalid token: {e}")


def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage."""
    return hashlib.sha256(api_key.encode()).hexdigest()


def generate_api_key() -> str:
    """Generate a secure API key."""
    return f"sk_{secrets.token_urlsafe(32)}"


def verify_api_key(provided_key: str, stored_hash: str) -> bool:
    """Verify an API key against its stored hash."""
    provided_hash = hash_api_key(provided_key)
    return hmac.compare_digest(provided_hash, stored_hash)
