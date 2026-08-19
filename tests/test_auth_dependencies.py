import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.auth.dependencies import CurrentHousehold
from app.auth.tokens import create_access_token
from app.database import get_db
from app.models import Household, HouseholdMember


@pytest.fixture
def household_client(engine):
    scoped_app = FastAPI()

    @scoped_app.get("/households/{household_id}/probe")
    def probe(household: CurrentHousehold):
        return {"id": household.id, "name": household.name}

    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    scoped_app.dependency_overrides[get_db] = override_get_db
    with TestClient(scoped_app) as test_client:
        yield test_client


@pytest.fixture
def bearer(user):
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


@pytest.fixture
def household(db, user):
    household = Household(name="Maison")
    household.members.append(HouseholdMember(user_id=user.id))
    db.add(household)
    db.commit()
    db.refresh(household)
    return household


def test_current_household_returns_a_household_the_user_belongs_to(
    household_client, household, bearer
):
    response = household_client.get(f"/households/{household.id}/probe", headers=bearer)

    assert response.status_code == 200
    assert response.json() == {"id": household.id, "name": "Maison"}


def test_current_household_hides_a_household_the_user_is_not_a_member_of(
    household_client, db, bearer
):
    foreign = Household(name="Chez les autres")
    db.add(foreign)
    db.commit()

    response = household_client.get(f"/households/{foreign.id}/probe", headers=bearer)

    assert response.status_code == 404
    assert response.json()["detail"] == "Household not found"


def test_current_household_answers_404_and_never_403_on_a_missing_household(
    household_client, bearer
):
    response = household_client.get("/households/404404/probe", headers=bearer)

    assert response.status_code == 404


def test_current_household_requires_authentication(household_client, household):
    response = household_client.get(f"/households/{household.id}/probe")

    assert response.status_code == 401
