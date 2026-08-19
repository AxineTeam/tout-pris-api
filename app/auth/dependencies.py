from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.tokens import read_access_token_subject
from app.database import get_db
from app.models import Household, HouseholdMember, User

bearer_scheme = HTTPBearer(auto_error=False, description="Access token returned by /auth/login")

DbSession = Annotated[Session, Depends(get_db)]
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


def get_current_user(db: DbSession, credentials: BearerCredentials) -> User:
    unauthenticated = HTTPException(
        status_code=401,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthenticated
    user_id = read_access_token_subject(credentials.credentials)
    if user_id is None:
        raise unauthenticated
    user = db.get(User, user_id)
    if user is None:
        raise unauthenticated
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_household(household_id: int, db: DbSession, user: CurrentUser) -> Household:
    household = db.scalar(
        select(Household)
        .join(HouseholdMember, HouseholdMember.household_id == Household.id)
        .where(Household.id == household_id, HouseholdMember.user_id == user.id)
    )
    if household is None:
        raise HTTPException(status_code=404, detail="Household not found")
    return household


CurrentHousehold = Annotated[Household, Depends(get_current_household)]
