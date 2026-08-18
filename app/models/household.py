import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class HouseholdRole(enum.StrEnum):
    owner = "owner"
    member = "member"


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"comment": "An account able to log in and edit the households it belongs to"}

    id: Mapped[int] = mapped_column(primary_key=True, comment="Surrogate primary key")
    email: Mapped[str] = mapped_column(
        unique=True, index=True, comment="Login address used to sign in"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="Signup timestamp"
    )

    memberships: Mapped[list["HouseholdMember"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Household(Base):
    __tablename__ = "households"
    __table_args__ = {"comment": "A group sharing its people, its item catalog and its trips"}

    id: Mapped[int] = mapped_column(primary_key=True, comment="Surrogate primary key")
    name: Mapped[str] = mapped_column(comment="Display name given by the members")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="Creation timestamp"
    )

    members: Mapped[list["HouseholdMember"]] = relationship(
        back_populates="household", cascade="all, delete-orphan"
    )
    persons: Mapped[list["Person"]] = relationship(
        back_populates="household", cascade="all, delete-orphan"
    )


class HouseholdMember(Base):
    __tablename__ = "household_members"
    __table_args__ = (
        UniqueConstraint("household_id", "user_id", name="uq_household_members"),
        {"comment": "Access of an account to a household"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, comment="Surrogate primary key")
    household_id: Mapped[int] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"),
        index=True,
        comment="Household the membership grants access to",
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        comment="Account granted access to the household",
    )
    role: Mapped[HouseholdRole] = mapped_column(
        Enum(HouseholdRole, name="household_role"),
        default=HouseholdRole.member,
        comment="Reserved for a later differentiation of rights",
    )

    household: Mapped[Household] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")


class Person(Base):
    __tablename__ = "persons"
    __table_args__ = (
        UniqueConstraint("household_id", "user_id", name="uq_persons_user"),
        {"comment": "Someone a trip is prepared for, whether or not they have an account"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, comment="Surrogate primary key")
    household_id: Mapped[int] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"),
        index=True,
        comment="Household the person belongs to",
    )
    name: Mapped[str] = mapped_column(comment="Display name shown in every 'who is it for' picker")
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        comment="Account of the person when they have one",
    )

    household: Mapped[Household] = relationship(back_populates="persons")
    user: Mapped[User | None] = relationship()
