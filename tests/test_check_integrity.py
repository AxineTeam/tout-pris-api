import io

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from accounts.models import User
from households.memberships import create_household
from households.models import Household, HouseholdMember, Person

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
    HouseholdMember.objects.filter(household=shared, user=camille).delete()
    Person.objects.create(household=shared, name="Personne", user=None)

    report = failing_check_integrity()

    assert "Camille" in report
    assert "Personne" not in report


def test_a_member_without_a_person_is_not_a_forbidden_state(camille, shared):
    shared.persons.all().delete()

    assert check_integrity() == ""


def test_every_forbidden_state_is_reported_in_one_run(camille):
    orphan = Household.objects.create(name="Chez personne")
    camille.personal_household.delete()

    report = failing_check_integrity()

    assert "camille@example.com" in report
    assert f"#{orphan.pk}" in report
