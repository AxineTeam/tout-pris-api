from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.auth.tokens import create_access_token, hash_refresh_token
from app.models import Identity, IdentityProvider, RefreshToken, User

NEW_ACCOUNT = {"email": "newcomer@example.com", "password": "a-long-enough-password"}


def test_register_returns_a_token_pair_and_creates_a_password_identity(client, db):
    response = client.post("/auth/register", json=NEW_ACCOUNT)

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]

    user = db.scalar(select(User).where(User.email == NEW_ACCOUNT["email"]))
    identity = db.scalar(select(Identity).where(Identity.user_id == user.id))
    assert identity.provider is IdentityProvider.password
    assert identity.provider_uid == NEW_ACCOUNT["email"]
    assert identity.secret != NEW_ACCOUNT["password"]


def test_register_does_not_create_a_household(client, db):
    client.post("/auth/register", json=NEW_ACCOUNT)

    user = db.scalar(select(User).where(User.email == NEW_ACCOUNT["email"]))
    assert user.memberships == []


def test_register_stores_the_refresh_token_hashed(client, db):
    response = client.post("/auth/register", json=NEW_ACCOUNT)

    stored = db.scalars(select(RefreshToken)).all()
    assert len(stored) == 1
    assert stored[0].token_hash == hash_refresh_token(response.json()["refresh_token"])


def test_register_rejects_an_email_already_taken(client, user):
    response = client.post("/auth/register", json={"email": user.email, "password": "another-one"})

    assert response.status_code == 409
    assert response.json()["detail"] == "Email already registered"


def test_register_rejects_a_short_password(client):
    response = client.post(
        "/auth/register", json={"email": "short@example.com", "password": "1234"}
    )

    assert response.status_code == 422


def test_register_rejects_a_malformed_email(client):
    response = client.post("/auth/register", json={"email": "not-an-email", "password": "12345678"})

    assert response.status_code == 422


def test_register_rejects_an_oversized_password(client):
    response = client.post(
        "/auth/register", json={"email": "long@example.com", "password": "x" * 129}
    )

    assert response.status_code == 422


def test_login_returns_a_token_pair(client, user, credentials):
    response = client.post("/auth/login", json=credentials)

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"


def test_login_rejects_a_wrong_password(client, user, credentials):
    response = client.post("/auth/login", json={**credentials, "password": "wrong-one"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_login_rejects_an_unknown_email_with_the_very_same_message(client, user, credentials):
    response = client.post("/auth/login", json={**credentials, "email": "ghost@example.com"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_login_rejects_an_identity_without_a_secret(client, db, user, credentials):
    identity = db.scalars(select(Identity)).one()
    identity.secret = None
    db.commit()

    response = client.post("/auth/login", json=credentials)

    assert response.status_code == 401


def test_login_rejects_an_oversized_password(client, user, credentials):
    response = client.post("/auth/login", json={**credentials, "password": "x" * 129})

    assert response.status_code == 422


def test_refresh_rotates_the_refresh_token(client, db, user, credentials):
    issued = client.post("/auth/login", json=credentials).json()

    response = client.post("/auth/refresh", json={"refresh_token": issued["refresh_token"]})

    assert response.status_code == 200
    rotated = response.json()
    assert rotated["refresh_token"] != issued["refresh_token"]

    previous = db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_refresh_token(issued["refresh_token"])
        )
    )
    assert previous.revoked_at is not None


def test_refresh_rejects_a_token_already_rotated(client, user, credentials):
    issued = client.post("/auth/login", json=credentials).json()
    client.post("/auth/refresh", json={"refresh_token": issued["refresh_token"]})

    response = client.post("/auth/refresh", json={"refresh_token": issued["refresh_token"]})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid refresh token"


def test_refresh_rejects_an_unknown_token(client):
    response = client.post("/auth/refresh", json={"refresh_token": "never-issued"})

    assert response.status_code == 401


def test_refresh_rejects_an_expired_token(client, db, user, credentials):
    issued = client.post("/auth/login", json=credentials).json()
    stored = db.scalars(select(RefreshToken)).one()
    stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()

    response = client.post("/auth/refresh", json={"refresh_token": issued["refresh_token"]})

    assert response.status_code == 401


def test_logout_revokes_the_refresh_token(client, db, user, credentials):
    issued = client.post("/auth/login", json=credentials).json()

    response = client.post("/auth/logout", json={"refresh_token": issued["refresh_token"]})

    assert response.status_code == 204
    assert db.scalars(select(RefreshToken)).one().revoked_at is not None
    assert (
        client.post("/auth/refresh", json={"refresh_token": issued["refresh_token"]}).status_code
        == 401
    )


def test_logout_is_idempotent_and_silent_on_an_unknown_token(client, user, credentials):
    issued = client.post("/auth/login", json=credentials).json()
    client.post("/auth/logout", json={"refresh_token": issued["refresh_token"]})

    assert (
        client.post("/auth/logout", json={"refresh_token": issued["refresh_token"]}).status_code
        == 204
    )
    assert client.post("/auth/logout", json={"refresh_token": "never-issued"}).status_code == 204


def test_me_returns_the_authenticated_account(authenticated_client, user):
    response = authenticated_client.get("/auth/me")

    assert response.status_code == 200
    body = response.json()
    assert body == {"id": user.id, "email": user.email, "created_at": body["created_at"]}


def test_me_rejects_a_request_without_a_bearer(client):
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_me_rejects_a_non_bearer_authorization_header(client):
    response = client.get("/auth/me", headers={"Authorization": "Basic Zm9vOmJhcg=="})

    assert response.status_code == 401


def test_me_rejects_a_forged_token(client):
    response = client.get("/auth/me", headers={"Authorization": "Bearer not.a.jwt"})

    assert response.status_code == 401


def test_me_rejects_a_token_of_a_deleted_account(client, db, user):
    token = create_access_token(user.id)
    db.delete(user)
    db.commit()

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
