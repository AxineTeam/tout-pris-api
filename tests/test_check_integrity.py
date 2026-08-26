import datetime
import io

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from accounts.models import User
from catalog.models import ItemStatus, ItemType, Kit, KitItem
from households.memberships import create_household
from households.models import Household, HouseholdMember, Person
from trips.models import Trip, TripItem, TripParticipant

pytestmark = pytest.mark.django_db


def check_integrity():
    output = io.StringIO()
    call_command("check_integrity", stdout=output)
    return output.getvalue()


def failing_check_integrity():
    output = io.StringIO()
    with pytest.raises(CommandError):
        call_command("check_integrity", stdout=output)
    return output.getvalue()


@pytest.fixture
def camille():
    user = User.objects.create_user(
        username="camille", email="camille@example.com", first_name="Camille"
    )
    create_household("camille", user, personal_of=user)
    return user


@pytest.fixture
def shared(camille):
    return create_household("Famille Martin", camille)


def test_a_healthy_database_says_nothing(camille, shared):
    assert check_integrity() == ""


def test_an_account_without_a_personal_household_is_listed(camille):
    camille.personal_household.delete()

    report = failing_check_integrity()

    assert "camille@example.com" in report
    assert "personal household" in report


def test_a_shared_household_without_a_member_is_listed(camille, shared):
    shared.members.all().delete()

    report = failing_check_integrity()

    assert "Famille Martin" in report
    assert f"#{shared.pk}" in report


def test_a_person_whose_account_left_the_household_is_listed(camille, shared):
    sacha = User.objects.create_user(username="sacha", email="sacha@example.com")
    HouseholdMember.objects.create(household=shared, user=sacha)
    HouseholdMember.objects.filter(household=shared, user=camille).delete()
    Person.objects.create(household=shared, name="Personne", user=None)

    report = failing_check_integrity()

    assert "Camille" in report
    assert "Personne" not in report
    assert "Famille Martin" not in report


def test_an_administration_account_is_not_expected_to_have_a_personal_household():
    User.objects.create_superuser(username="root", email="root@example.com", password="x")
    User.objects.create_user(username="staff", email="staff@example.com", is_staff=True)

    assert check_integrity() == ""


def test_a_member_without_a_person_is_not_a_forbidden_state(camille, shared):
    shared.persons.all().delete()

    assert check_integrity() == ""


def test_every_forbidden_state_is_reported_in_one_run(camille):
    orphan = Household.objects.create(name="Chez personne")
    camille.personal_household.delete()

    report = failing_check_integrity()

    assert "camille@example.com" in report
    assert f"#{orphan.pk}" in report


def test_a_kit_line_whose_item_type_belongs_to_another_household_is_listed(camille, shared):
    elsewhere = Household.objects.create(name="Chez les grands-parents")
    kit = Kit.objects.create(household=shared, name="Sac a langer")
    KitItem.objects.create(
        kit=kit, item_type=ItemType.objects.create(household=elsewhere, name="Bavoir")
    )

    assert "Bavoir" in failing_check_integrity()


def test_a_kit_line_whose_person_belongs_to_another_household_is_listed(camille, shared):
    elsewhere = Household.objects.create(name="Chez les grands-parents")
    kit = Kit.objects.create(household=shared, name="Affaires enfants")
    KitItem.objects.create(
        kit=kit,
        item_type=ItemType.objects.create(household=shared, name="T-shirt"),
        person=Person.objects.create(household=elsewhere, name="Enfant 1"),
    )

    assert "T-shirt" in failing_check_integrity()


def test_a_kit_line_of_its_own_household_is_not_a_forbidden_state(camille, shared):
    kit = Kit.objects.create(household=shared, name="Sac a langer")
    KitItem.objects.create(
        kit=kit,
        item_type=ItemType.objects.create(household=shared, name="Bavoir"),
        person=Person.objects.create(household=shared, name="Enfant 1"),
    )

    assert check_integrity() == ""


def test_a_household_whose_statuses_lost_their_default_one_is_listed(camille, shared):
    status = ItemStatus.objects.create(household=shared, name="Dans les sacs", color="#22c55e")
    ItemStatus.objects.filter(pk=status.pk).update(is_default=False)

    assert "Famille Martin" in failing_check_integrity()


def test_a_household_that_holds_no_status_at_all_is_not_a_forbidden_state(camille, shared):
    assert not shared.item_statuses.exists()
    assert check_integrity() == ""


def make_trip(household):
    return Trip.objects.create(
        household=household,
        name="Une semaine en Bretagne",
        date=datetime.date(2026, 7, 4),
    )


def make_status(household):
    return ItemStatus.objects.create(household=household, name="Pas prepare", color="#94a3b8")


def test_a_trip_line_whose_item_type_belongs_to_another_household_is_listed(camille, shared):
    elsewhere = Household.objects.create(name="Chez les grands-parents")
    TripItem.objects.create(
        trip=make_trip(shared),
        item_type=ItemType.objects.create(household=elsewhere, name="T-shirt"),
        status=make_status(shared),
    )

    assert "T-shirt" in failing_check_integrity()


def test_a_trip_line_whose_person_belongs_to_another_household_is_listed(camille, shared):
    elsewhere = Household.objects.create(name="Chez les grands-parents")
    TripItem.objects.create(
        trip=make_trip(shared),
        item_type=ItemType.objects.create(household=shared, name="T-shirt"),
        status=make_status(shared),
        person=Person.objects.create(household=elsewhere, name="Enfant 1"),
    )

    assert "T-shirt" in failing_check_integrity()


def test_a_trip_line_whose_status_belongs_to_another_household_is_listed(camille, shared):
    elsewhere = Household.objects.create(name="Chez les grands-parents")
    TripItem.objects.create(
        trip=make_trip(shared),
        item_type=ItemType.objects.create(household=shared, name="Bavoir"),
        status=make_status(elsewhere),
    )

    assert "Bavoir" in failing_check_integrity()


def test_a_trip_line_of_its_own_household_is_not_a_forbidden_state(camille, shared):
    TripItem.objects.create(
        trip=make_trip(shared),
        item_type=ItemType.objects.create(household=shared, name="Bavoir"),
        status=make_status(shared),
        person=Person.objects.create(household=shared, name="Enfant 1"),
    )

    assert check_integrity() == ""


def test_a_participant_from_another_household_is_listed(camille, shared):
    elsewhere = Household.objects.create(name="Chez les grands-parents")
    TripParticipant.objects.create(
        trip=make_trip(shared),
        person=Person.objects.create(household=elsewhere, name="Enfant 1"),
    )

    assert "Enfant 1" in failing_check_integrity()


def test_a_participant_of_the_household_of_the_trip_is_not_a_forbidden_state(camille, shared):
    TripParticipant.objects.create(
        trip=make_trip(shared), person=Person.objects.create(household=shared, name="Enfant 1")
    )

    assert check_integrity() == ""
