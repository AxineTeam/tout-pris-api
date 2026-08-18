import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Household, HouseholdMember, HouseholdRole, Person, User


@pytest.fixture
def household(db):
    household = Household(name="Chez nous")
    db.add(household)
    db.commit()
    return household


@pytest.fixture
def user(db):
    user = User(email="parent1@example.com")
    db.add(user)
    db.commit()
    return user


def test_user_email_is_unique(db, user):
    db.add(User(email=user.email))

    with pytest.raises(IntegrityError):
        db.flush()


def test_member_role_defaults_to_member(db, household, user):
    member = HouseholdMember(household=household, user=user)
    db.add(member)
    db.commit()

    assert member.role is HouseholdRole.member


def test_user_belongs_to_a_household_only_once(db, household, user):
    db.add(HouseholdMember(household=household, user=user))
    db.commit()
    db.add(HouseholdMember(household=household, user=user, role=HouseholdRole.owner))

    with pytest.raises(IntegrityError):
        db.flush()


def test_user_can_belong_to_several_households(db, household, user):
    other_household = Household(name="Chez les grands-parents")
    db.add_all(
        [
            HouseholdMember(household=household, user=user),
            HouseholdMember(household=other_household, user=user),
        ]
    )
    db.commit()

    assert len(user.memberships) == 2


def test_persons_without_account_coexist(db, household):
    db.add_all(
        [
            Person(household=household, name="Enfant 1"),
            Person(household=household, name="Enfant 2"),
        ]
    )
    db.commit()

    assert len(household.persons) == 2


def test_account_is_linked_to_a_single_person_per_household(db, household, user):
    db.add(Person(household=household, name="Parent 1", user=user))
    db.commit()
    db.add(Person(household=household, name="Parent 1 bis", user=user))

    with pytest.raises(IntegrityError):
        db.flush()


def test_deleting_a_household_deletes_its_members_and_persons(db, household, user):
    db.add_all(
        [
            HouseholdMember(household=household, user=user),
            Person(household=household, name="Enfant 1"),
        ]
    )
    db.commit()

    db.delete(household)
    db.commit()

    assert db.query(HouseholdMember).count() == 0
    assert db.query(Person).count() == 0
    assert db.query(User).count() == 1


def test_deleting_a_user_keeps_the_person_and_clears_the_account_link(db, household, user):
    person = Person(household=household, name="Parent 1", user=user)
    db.add_all([person, HouseholdMember(household=household, user=user)])
    db.commit()

    db.delete(user)
    db.commit()
    db.refresh(person)

    assert person.user_id is None
    assert db.query(HouseholdMember).count() == 0
