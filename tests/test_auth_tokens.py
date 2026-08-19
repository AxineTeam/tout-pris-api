from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import select

from app.auth.passwords import (
    UNMATCHABLE_HASH,
    equalize_verification_time,
    hash_password,
    verify_password,
)
from app.auth.tokens import (
    ACCESS_TOKEN_ALGORITHM,
    as_utc,
    create_access_token,
    create_refresh_token,
    find_usable_refresh_token,
    hash_refresh_token,
    read_access_token_subject,
    revoke_refresh_token,
)
from app.config import settings
from app.models import RefreshToken


def forge(payload: dict, key: str = settings.secret_key) -> str:
    return jwt.encode(payload, key, algorithm=ACCESS_TOKEN_ALGORITHM)


def test_hash_password_is_salted_and_verifiable():
    first = hash_password("a-long-enough-password")
    second = hash_password("a-long-enough-password")

    assert first != second
    assert first.startswith("$argon2")
    assert verify_password("a-long-enough-password", first)
    assert not verify_password("another-password", first)


def test_access_token_round_trip():
    assert read_access_token_subject(create_access_token(42)) == 42


@pytest.mark.parametrize(
    "token",
    [
        "not-a-jwt",
        forge({"sub": "1"}, key="another-secret"),
        forge({"iat": datetime.now(UTC)}),
        forge({"sub": "not-a-number"}),
        forge({"sub": "1", "exp": datetime.now(UTC) - timedelta(minutes=1)}),
    ],
)
def test_read_access_token_subject_refuses_anything_it_did_not_sign(token):
    assert read_access_token_subject(token) is None


def test_hash_refresh_token_never_returns_the_token():
    token = "an-opaque-token"

    assert hash_refresh_token(token) != token
    assert hash_refresh_token(token) == hash_refresh_token(token)


def test_create_refresh_token_stores_only_its_hash(db, user):
    token = create_refresh_token(db, user)
    db.commit()

    stored = db.scalars(select(RefreshToken)).one()
    assert token not in stored.token_hash
    assert stored.token_hash == hash_refresh_token(token)
    assert stored.user_id == user.id


def test_find_usable_refresh_token_returns_the_stored_row(db, user):
    token = create_refresh_token(db, user)
    db.commit()

    assert find_usable_refresh_token(db, token) is not None


def test_find_usable_refresh_token_ignores_an_unknown_token(db):
    assert find_usable_refresh_token(db, "never-issued") is None


def test_find_usable_refresh_token_ignores_a_revoked_token(db, user):
    token = create_refresh_token(db, user)
    db.commit()
    revoke_refresh_token(db.scalars(select(RefreshToken)).one())
    db.commit()

    assert find_usable_refresh_token(db, token) is None


def test_find_usable_refresh_token_ignores_an_expired_token(db, user):
    token = create_refresh_token(db, user)
    db.commit()
    db.scalars(select(RefreshToken)).one().expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()

    assert find_usable_refresh_token(db, token) is None


def test_equalize_verification_time_can_never_match_a_password():
    assert not verify_password("any-password", UNMATCHABLE_HASH)
    assert equalize_verification_time("any-password") is None


def test_as_utc_assumes_utc_for_the_naive_datetimes_sqlite_gives_back():
    naive = datetime(2026, 1, 1, 12, 0, 0)
    aware = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    assert as_utc(naive) == aware
    assert as_utc(aware) is aware
