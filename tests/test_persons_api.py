import pytest
from django.test import Client

from accounts.models import User
from households.models import Household, HouseholdMember, Person

pytestmark = pytest.mark.django_db


def persons_url(household):
    return f"/api/households/{household.pk}/persons/"


def person_url(household, person):
    return f"{persons_url(household)}{person.pk}/"


@pytest.fixture
def camille():
    return User.objects.create_user(
        username="camille", email="camille@example.com", first_name="Camille"
    )


@pytest.fixture
def household(camille):
    shared = Household.objects.create(name="Famille Martin")
    HouseholdMember.objects.create(household=shared, user=camille)
    Person.objects.create(household=shared, user=camille, name="Camille")
    return shared


@pytest.fixture
def client(camille):
    signed_in = Client()
    signed_in.force_login(camille)
    return signed_in


@pytest.fixture
def stranger_household():
    stranger = User.objects.create_user(username="sacha", email="sacha@example.com")
    other = Household.objects.create(name="Chez les autres")
    HouseholdMember.objects.create(household=other, user=stranger)
    return other


def test_the_persons_of_a_household_are_listed(client, household):
    Person.objects.create(household=household, name="Jeanne")

    listed = client.get(persons_url(household)).json()

    assert [person["name"] for person in listed] == ["Camille", "Jeanne"]
    assert listed[1]["user"] is None


def test_creating_a_person_adds_them_to_the_household(client, household):
    response = client.post(
        persons_url(household), {"name": "Jeanne"}, content_type="application/json"
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Jeanne"
    assert household.persons.filter(name="Jeanne", user=None).exists()


def test_a_person_is_read_one_by_one(client, household):
    jeanne = Person.objects.create(household=household, name="Jeanne")

    response = client.get(person_url(household, jeanne))

    assert response.status_code == 200
    assert response.json() == {"id": jeanne.pk, "name": "Jeanne", "user": None}


def test_renaming_a_person_keeps_their_account(client, household, camille):
    person = household.persons.get(user=camille)

    response = client.patch(
        person_url(household, person), {"name": "Maman"}, content_type="application/json"
    )

    assert response.status_code == 200
    person.refresh_from_db()
    assert (person.name, person.user) == ("Maman", camille)


def test_a_person_without_an_account_is_deleted(client, household):
    jeanne = Person.objects.create(household=household, name="Jeanne")

    response = client.delete(person_url(household, jeanne))

    assert response.status_code == 204
    assert not Person.objects.filter(pk=jeanne.pk).exists()


def test_a_person_whose_account_is_still_a_member_is_not_deleted(client, household, camille):
    person = household.persons.get(user=camille)

    response = client.delete(person_url(household, person))

    assert response.status_code == 409
    assert Person.objects.filter(pk=person.pk).exists()


def test_the_personal_household_has_persons_too(client, camille):
    personal = Household.objects.create(name="camille", personal_of=camille)
    HouseholdMember.objects.create(household=personal, user=camille)

    created = client.post(persons_url(personal), {"name": "Moi"}, content_type="application/json")

    assert created.status_code == 201
    assert [person["name"] for person in client.get(persons_url(personal)).json()] == ["Moi"]


def test_the_persons_of_another_household_are_out_of_reach(client, stranger_household):
    theirs = Person.objects.create(household=stranger_household, name="Inconnu")

    assert client.get(persons_url(stranger_household)).status_code == 404
    assert (
        client.post(
            persons_url(stranger_household), {"name": "Jeanne"}, content_type="application/json"
        ).status_code
        == 404
    )
    assert client.get(person_url(stranger_household, theirs)).status_code == 404
    assert (
        client.patch(
            person_url(stranger_household, theirs),
            {"name": "Jeanne"},
            content_type="application/json",
        ).status_code
        == 404
    )
    assert client.delete(person_url(stranger_household, theirs)).status_code == 404


def test_a_person_of_another_household_is_unreachable_through_our_own(
    client, household, stranger_household
):
    theirs = Person.objects.create(household=stranger_household, name="Inconnu")

    assert client.get(person_url(household, theirs)).status_code == 404


def test_the_person_endpoints_refuse_an_unauthenticated_caller(household):
    anonymous = Client()

    assert anonymous.get(persons_url(household)).status_code == 401
    assert anonymous.post(persons_url(household), {"name": "Jeanne"}).status_code == 401


def test_a_rename_whose_body_is_not_an_object_is_refused(client, household):
    jeanne = Person.objects.create(household=household, name="Jeanne")

    response = client.patch(person_url(household, jeanne), [], content_type="application/json")

    assert response.status_code == 400
