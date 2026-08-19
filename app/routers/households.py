from fastapi import APIRouter
from sqlalchemy import select

from app.auth.dependencies import CurrentHousehold, CurrentUser, DbSession
from app.models import Household, HouseholdMember, HouseholdRole
from app.schemas import HouseholdCreate, HouseholdRead, HouseholdUpdate

router = APIRouter(prefix="/households", tags=["households"])


@router.post(
    "",
    response_model=HouseholdRead,
    status_code=201,
    summary="Create a household owned by the authenticated account",
)
def create_household(payload: HouseholdCreate, db: DbSession, user: CurrentUser) -> Household:
    household = Household(name=payload.name)
    household.members.append(HouseholdMember(user=user, role=HouseholdRole.owner))
    db.add(household)
    db.commit()
    db.refresh(household)
    return household


@router.get(
    "",
    response_model=list[HouseholdRead],
    summary="List the households the authenticated account belongs to",
)
def list_households(db: DbSession, user: CurrentUser) -> list[Household]:
    return list(
        db.scalars(
            select(Household)
            .join(HouseholdMember, HouseholdMember.household_id == Household.id)
            .where(HouseholdMember.user_id == user.id)
            .order_by(Household.id)
        )
    )


@router.get("/{household_id}", response_model=HouseholdRead, summary="Get a household by id")
def read_household(household: CurrentHousehold) -> Household:
    return household


@router.patch("/{household_id}", response_model=HouseholdRead, summary="Rename a household")
def update_household(
    payload: HouseholdUpdate, household: CurrentHousehold, db: DbSession
) -> Household:
    if payload.name is not None:
        household.name = payload.name
    db.commit()
    db.refresh(household)
    return household


@router.delete("/{household_id}", status_code=204, summary="Delete a household and its content")
def delete_household(household: CurrentHousehold, db: DbSession) -> None:
    db.delete(household)
    db.commit()
