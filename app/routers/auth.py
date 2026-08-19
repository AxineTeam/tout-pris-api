from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, DbSession
from app.auth.passwords import equalize_verification_time, hash_password, verify_password
from app.auth.tokens import (
    create_access_token,
    create_refresh_token,
    find_usable_refresh_token,
    revoke_refresh_token,
)
from app.models import Identity, IdentityProvider, User
from app.schemas import RefreshTokenRequest, TokenPair, UserCreate, UserLogin, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])

INVALID_CREDENTIALS = "Invalid credentials"
INVALID_REFRESH_TOKEN = "Invalid refresh token"


def issue_token_pair(db: Session, user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(db, user),
    )


def find_password_identity(db: Session, email: str) -> Identity | None:
    return db.scalar(
        select(Identity).where(
            Identity.provider == IdentityProvider.password,
            Identity.provider_uid == email,
        )
    )


@router.post(
    "/register",
    response_model=TokenPair,
    status_code=201,
    summary="Create an account from an email and a password",
)
def register(payload: UserCreate, db: DbSession) -> TokenPair:
    user = User(email=payload.email)
    user.identities.append(
        Identity(
            provider=IdentityProvider.password,
            provider_uid=payload.email,
            secret=hash_password(payload.password),
        )
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email already registered") from None
    tokens = issue_token_pair(db, user)
    db.commit()
    return tokens


@router.post("/login", response_model=TokenPair, summary="Exchange credentials for a token pair")
def login(payload: UserLogin, db: DbSession) -> TokenPair:
    identity = find_password_identity(db, payload.email)
    if identity is None or identity.secret is None:
        equalize_verification_time(payload.password)
        raise HTTPException(status_code=401, detail=INVALID_CREDENTIALS)
    if not verify_password(payload.password, identity.secret):
        raise HTTPException(status_code=401, detail=INVALID_CREDENTIALS)

    tokens = issue_token_pair(db, identity.user)
    db.commit()
    return tokens


@router.post("/refresh", response_model=TokenPair, summary="Rotate a refresh token")
def refresh(payload: RefreshTokenRequest, db: DbSession) -> TokenPair:
    stored = find_usable_refresh_token(db, payload.refresh_token)
    if stored is None:
        raise HTTPException(status_code=401, detail=INVALID_REFRESH_TOKEN)

    revoke_refresh_token(stored)
    tokens = issue_token_pair(db, stored.user)
    db.commit()
    return tokens


@router.post("/logout", status_code=204, summary="Revoke a refresh token")
def logout(payload: RefreshTokenRequest, db: DbSession) -> None:
    stored = find_usable_refresh_token(db, payload.refresh_token)
    if stored is not None:
        revoke_refresh_token(stored)
        db.commit()


@router.get("/me", response_model=UserRead, summary="Get the authenticated account")
def read_me(user: CurrentUser) -> User:
    return user
