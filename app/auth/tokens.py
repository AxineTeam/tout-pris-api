import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import RefreshToken, User

ACCESS_TOKEN_ALGORITHM = "HS256"
REFRESH_TOKEN_BYTES = 32


def as_utc(moment: datetime) -> datetime:
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def create_access_token(user_id: int) -> str:
    issued_at = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=settings.access_token_ttl_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ACCESS_TOKEN_ALGORITHM)


def read_access_token_subject(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ACCESS_TOKEN_ALGORITHM])
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        return None


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_refresh_token(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(REFRESH_TOKEN_BYTES)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(token),
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days),
        )
    )
    return token


def find_usable_refresh_token(db: Session, token: str) -> RefreshToken | None:
    stored = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(token))
    )
    if stored is None or stored.revoked_at is not None:
        return None
    if as_utc(stored.expires_at) <= datetime.now(UTC):
        return None
    return stored


def revoke_refresh_token(stored: RefreshToken) -> None:
    stored.revoked_at = datetime.now(UTC)
