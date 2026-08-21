import pytest
from django.test import Client

from accounts.models import User
from households.models import Household, HouseholdMember, Person

pytestmark = pytest.mark.django_db


def members_url(household):
    return f"/api/households/{household.pk}/members/"


def member_url(household, member):
    return f"{members_url(household)}{member.pk}/"


def signed_in(user):
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def camille():
    return User.objects.create_user(
        username="camille", email="camille@example.com", first_name="Camille"
    )


@pytest.fixture
def sacha():
    return User.objects.create_user(username="sacha", email="sacha@example.com", first_name="Sacha")


@pytest.fixture
def household(camille):
    shared = Household.objects.create(name="Famille Martin")
    HouseholdMember.objects.create(household=shared, user=camille, role="owner")
    Person.objects.create(household=shared, user=camille, name="Camille")
    return shared


@pytest.fixture
def joined(household, sacha):
    Person.objects.create(household=household, user=sacha, name="Sacha")
    return HouseholdMember.objects.create(household=household, user=sacha)


@pytest.fixture
def client(camille):
    return signed_in(camille)


def test_the_members_of_a_household_are_listed_with_their_address(client, household, joined):
    listed = client.get(members_url(household)).json()

    assert [(member["email"], member["role"]) for member in listed] == [
        ("camille@example.com", "owner"),
        ("sacha@example.com", "member"),
    ]


def test_removing_a_member_keeps_their_person_and_unlinks_their_account(
    client, household, joined, sacha
):
    response = client.delete(member_url(household, joined))

    assert response.status_code == 204
    assert not HouseholdMember.objects.filter(pk=joined.pk).exists()
    person = household.persons.get(name="Sacha")
    assert person.user is None


def test_a_member_leaves_the_household_by_removing_their_own_membership(household, joined, sacha):
    response = signed_in(sacha).delete(member_url(household, joined))

    assert response.status_code == 204
    assert not Household.objects.filter(pk=household.pk, members__user=sacha).exists()


def test_the_last_member_cannot_leave_and_is_told_to_delete_the_household(
    client, household, camille
):
    only = household.members.get()

    response = client.delete(member_url(household, only))

    assert response.status_code == 409
    assert HouseholdMember.objects.filter(pk=only.pk).exists()


def test_the_members_of_another_household_are_out_of_reach(client):
    stranger = User.objects.create_user(username="alex", email="alex@example.com")
    other = Household.objects.create(name="Chez les autres")
    theirs = HouseholdMember.objects.create(household=other, user=stranger)

    assert client.get(members_url(other)).status_code == 404
    assert client.delete(member_url(other, theirs)).status_code == 404


def test_a_personal_household_has_no_members_to_speak_of(client, camille):
    personal = Household.objects.create(name="camille", personal_of=camille)
    only = HouseholdMember.objects.create(household=personal, user=camille)

    assert client.get(members_url(personal)).status_code == 404
    assert client.delete(member_url(personal, only)).status_code == 404


def test_the_member_endpoints_refuse_an_unauthenticated_caller(household, joined):
    anonymous = Client()

    assert anonymous.get(members_url(household)).status_code == 401
    assert anonymous.delete(member_url(household, joined)).status_code == 401
