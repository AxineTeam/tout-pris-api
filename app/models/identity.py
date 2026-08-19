import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.household import User


class IdentityProvider(enum.StrEnum):
    password = "password"
    google = "google"
    facebook = "facebook"
    github = "github"


class Identity(Base):
    __tablename__ = "identities"
    __table_args__ = (
        UniqueConstraint("provider", "provider_uid", name="uq_identities_provider_uid"),
        {"comment": "A way of signing in as an account, one row per provider"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, comment="Surrogate primary key")
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        comment="Account the identity signs in as",
    )
    provider: Mapped[IdentityProvider] = mapped_column(
        Enum(IdentityProvider, name="identity_provider"),
        comment="Authentication provider vouching for the identity",
    )
    provider_uid: Mapped[str] = mapped_column(
        comment="Email address for the password provider, provider account id otherwise"
    )
    secret: Mapped[str | None] = mapped_column(
        comment="Argon2 hash of the password for the password provider, NULL otherwise"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="Link timestamp"
    )

    user: Mapped[User] = relationship(back_populates="identities")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = {"comment": "A revocable opaque token exchangeable for a fresh access token"}

    id: Mapped[int] = mapped_column(primary_key=True, comment="Surrogate primary key")
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        comment="Account whose session the token extends",
    )
    token_hash: Mapped[str] = mapped_column(
        unique=True,
        index=True,
        comment="SHA-256 hex digest of the token, the token itself is never stored",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), comment="Moment past which the token is refused"
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Moment the token was rotated or logged out, NULL while it is usable",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="Issue timestamp"
    )

    user: Mapped[User] = relationship(back_populates="refresh_tokens")
