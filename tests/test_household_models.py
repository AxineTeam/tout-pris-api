import pytest
from django.db import IntegrityError

from accounts.models import User
from households.models import Household, HouseholdMember, HouseholdRole, Invitation, Person

pytestmark = pytest.mark.django_db


@pytest.fixture
def household():
    return Household.objects.create(name="Chez nous")


@pytest.fixture
def user():
    return User.objects.create_user(username="parent1", email="parent1@example.com")


def test_a_household_is_named_after_its_display_name(household):
    assert str(household) == "Chez nous"


def test_a_person_is_named_after_its_display_name(household):
    person = Person.objects.create(household=household, name="Enfant 1")

    assert str(person) == "Enfant 1"


def test_a_membership_role_defaults_to_member(household, user):
    member = HouseholdMember.objects.create(household=household, user=user)
    member.refresh_from_db()

    assert member.role == HouseholdRole.MEMBER


def test_a_user_belongs_to_a_household_only_once(household, user):
    HouseholdMember.objects.create(household=household, user=user)

    with pytest.raises(IntegrityError):
        HouseholdMember.objects.create(household=household, user=user, role=HouseholdRole.OWNER)


def test_a_user_can_belong_to_several_households(household, user):
    other_household = Household.objects.create(name="Chez les grands-parents")
    HouseholdMember.objects.create(household=household, user=user)
    HouseholdMember.objects.create(household=other_household, user=user)

    assert user.memberships.count() == 2


def test_persons_without_an_account_coexist_in_a_household(household):
    Person.objects.create(household=household, name="Enfant 1")
    Person.objects.create(household=household, name="Enfant 2")

    assert household.persons.count() == 2


def test_an_account_is_linked_to_a_single_person_per_household(household, user):
    Person.objects.create(household=household, name="Parent 1", user=user)

    with pytest.raises(IntegrityError):
        Person.objects.create(household=household, name="Parent 1 bis", user=user)


def test_deleting_a_household_deletes_its_members_and_persons(household, user):
    HouseholdMember.objects.create(household=household, user=user)
    Person.objects.create(household=household, name="Enfant 1")

    household.delete()

    assert HouseholdMember.objects.count() == 0
    assert Person.objects.count() == 0
    assert User.objects.count() == 1


def test_deleting_a_user_keeps_the_person_and_clears_the_account_link(household, user):
    person = Person.objects.create(household=household, name="Parent 1", user=user)
    HouseholdMember.objects.create(household=household, user=user)

    user.delete()
    person.refresh_from_db()

    assert person.user_id is None
    assert HouseholdMember.objects.count() == 0


def test_an_invitation_is_named_after_its_address_and_household(household, user):
    invitation = Invitation.objects.create(
        household=household, email="guest@example.com", invited_by=user
    )

    assert str(invitation) == "guest@example.com to Chez nous"
