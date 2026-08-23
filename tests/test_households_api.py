import pytest
from django.test import Client

from accounts.models import User
from households.memberships import create_household
from households.models import Household, HouseholdMember, Person

pytestmark = pytest.mark.django_db

HOUSEHOLDS_URL = "/api/households/"


@pytest.fixture
def camille():
    user = User.objects.create_user(
        username="camille", email="camille@example.com", first_name="Camille"
    )
    create_household("camille", user, personal_of=user)
    return user


def signed_in(user):
    client = Client()
    client.force_login(user)
    return client


def test_the_personal_household_is_listed_and_says_it_is_personal(camille):
    listed = signed_in(camille).get(HOUSEHOLDS_URL).json()

    assert [(entry["name"], entry["personal"]) for entry in listed] == [("camille", True)]


def test_a_shared_household_is_listed_alongside_the_personal_one(camille):
    create_household("Famille Martin", camille)

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


def household_url(household):
    return f"{HOUSEHOLDS_URL}{household.pk}/"


def test_creating_a_shared_household_makes_its_creator_a_member_and_a_person(camille):
    response = signed_in(camille).post(
        HOUSEHOLDS_URL, {"name": "Famille Martin"}, content_type="application/json"
    )

    assert response.status_code == 201
    household = Household.objects.get(pk=response.json()["id"])
    assert response.json() == {"id": household.pk, "name": "Famille Martin", "personal": False}
    assert household.members.get(user=camille).role == "owner"
    assert household.persons.get(user=camille).name == "Camille"


def test_a_created_household_is_listed_after_the_personal_one(camille):
    client = signed_in(camille)
    client.post(HOUSEHOLDS_URL, {"name": "Famille Martin"}, content_type="application/json")

    listed = client.get(HOUSEHOLDS_URL).json()

    assert [entry["name"] for entry in listed] == ["camille", "Famille Martin"]


def test_a_shared_household_is_renamed(camille):
    shared = create_household("Famille Martin", camille)

    response = signed_in(camille).patch(
        household_url(shared), {"name": "Les Martin"}, content_type="application/json"
    )

    assert response.status_code == 200
    assert response.json() == {"id": shared.pk, "name": "Les Martin", "personal": False}


def test_a_rename_without_a_name_leaves_it_unchanged(camille):
    shared = create_household("Famille Martin", camille)
    client = signed_in(camille)

    empty = client.patch(household_url(shared), {}, content_type="application/json")
    explicit_null = client.patch(
        household_url(shared), {"name": None}, content_type="application/json"
    )

    assert (empty.status_code, explicit_null.status_code) == (200, 200)
    shared.refresh_from_db()
    assert shared.name == "Famille Martin"


def test_deleting_a_shared_household_takes_its_members_and_persons_with_it(camille):
    shared = create_household("Famille Martin", camille)
    Person.objects.create(household=shared, name="Jeanne")

    response = signed_in(camille).delete(household_url(shared))

    assert response.status_code == 204
    assert not Household.objects.filter(pk=shared.pk).exists()
    assert not HouseholdMember.objects.filter(household=shared.pk).exists()
    assert not Person.objects.filter(household=shared.pk).exists()


def test_the_personal_household_is_neither_renamed_nor_deleted(camille):
    personal = camille.personal_household
    client = signed_in(camille)

    renamed = client.patch(
        household_url(personal), {"name": "Chez moi"}, content_type="application/json"
    )

    assert renamed.status_code == 404
    assert client.delete(household_url(personal)).status_code == 404


def test_the_household_of_another_account_is_out_of_reach(camille):
    stranger = User.objects.create_user(username="sacha", email="sacha@example.com")
    theirs = Household.objects.create(name="Chez les autres")
    HouseholdMember.objects.create(household=theirs, user=stranger)
    client = signed_in(camille)

    renamed = client.patch(
        household_url(theirs), {"name": "À moi"}, content_type="application/json"
    )

    assert renamed.status_code == 404
    assert client.delete(household_url(theirs)).status_code == 404


def test_creating_a_household_refuses_an_unauthenticated_caller():
    response = Client().post(HOUSEHOLDS_URL, {"name": "Famille Martin"})

    assert response.status_code == 401


def test_a_rename_whose_body_is_not_an_object_is_refused(camille):
    shared = create_household("Famille Martin", camille)

    response = signed_in(camille).patch(household_url(shared), [], content_type="application/json")

    assert response.status_code == 400
