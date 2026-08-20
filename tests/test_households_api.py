import pytest
from django.test import Client

from accounts.models import User
from households.models import Household, HouseholdMember

pytestmark = pytest.mark.django_db

HOUSEHOLDS_URL = "/api/households/"


@pytest.fixture
def camille():
    user = User.objects.create_user(
        username="camille", email="camille@example.com", first_name="Camille"
    )
    Household.objects.create(name="camille", personal_of=user).members.create(user=user)
    return user


def signed_in(user):
    client = Client()
    client.force_login(user)
    return client


def test_the_personal_household_is_listed_and_says_it_is_personal(camille):
    listed = signed_in(camille).get(HOUSEHOLDS_URL).json()

    assert [(entry["name"], entry["personal"]) for entry in listed] == [("camille", True)]


def test_a_shared_household_is_listed_alongside_the_personal_one(camille):
    shared = Household.objects.create(name="Famille Martin")
    HouseholdMember.objects.create(household=shared, user=camille)

    listed = signed_in(camille).get(HOUSEHOLDS_URL).json()

    assert [(entry["name"], entry["personal"]) for entry in listed] == [
        ("camille", True),
        ("Famille Martin", False),
    ]


def test_the_households_of_other_accounts_are_never_listed(camille):
    stranger = User.objects.create_user(username="sacha", email="sacha@example.com")
    Household.objects.create(name="sacha", personal_of=stranger).members.create(user=stranger)

    listed = signed_in(camille).get(HOUSEHOLDS_URL).json()

    assert [entry["name"] for entry in listed] == ["camille"]


def test_an_unauthenticated_caller_is_told_to_authenticate(camille):
    response = Client().get(HOUSEHOLDS_URL)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Session"


def test_the_personal_household_comes_first_even_when_the_shared_one_is_older():
    older = Household.objects.create(name="Famille Martin")
    sacha = User.objects.create_user(username="sacha", email="sacha@example.com")
    Household.objects.create(name="sacha", personal_of=sacha).members.create(user=sacha)
    HouseholdMember.objects.create(household=older, user=sacha)

    listed = signed_in(sacha).get(HOUSEHOLDS_URL).json()

    assert [(entry["name"], entry["personal"]) for entry in listed] == [
        ("sacha", True),
        ("Famille Martin", False),
    ]
