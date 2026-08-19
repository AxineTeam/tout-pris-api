from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.auth.dependencies import CurrentHousehold, DbSession
from app.models import Person
from app.schemas import PersonCreate, PersonRead, PersonUpdate

router = APIRouter(prefix="/households/{household_id}/persons", tags=["persons"])


def get_household_person(person_id: int, household: CurrentHousehold, db: DbSession) -> Person:
    person = db.scalar(
        select(Person).where(Person.id == person_id, Person.household_id == household.id)
    )
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found")
    return person


HouseholdPerson = Annotated[Person, Depends(get_household_person)]


@router.post(
    "",
    response_model=PersonRead,
    status_code=201,
    summary="Add a person to the household",
)
def create_person(payload: PersonCreate, household: CurrentHousehold, db: DbSession) -> Person:
    person = Person(household_id=household.id, name=payload.name)
    db.add(person)
    db.commit()
    db.refresh(person)
    return person


@router.get("", response_model=list[PersonRead], summary="List the persons of the household")
def list_persons(household: CurrentHousehold, db: DbSession) -> list[Person]:
    return list(
        db.scalars(select(Person).where(Person.household_id == household.id).order_by(Person.id))
    )


@router.get("/{person_id}", response_model=PersonRead, summary="Get a person by id")
def read_person(person: HouseholdPerson) -> Person:
    return person


@router.patch("/{person_id}", response_model=PersonRead, summary="Rename a person")
def update_person(payload: PersonUpdate, person: HouseholdPerson, db: DbSession) -> Person:
    if payload.name is not None:
        person.name = payload.name
    db.commit()
    db.refresh(person)
    return person


@router.delete("/{person_id}", status_code=204, summary="Remove a person from the household")
def delete_person(person: HouseholdPerson, db: DbSession) -> None:
    db.delete(person)
    db.commit()
