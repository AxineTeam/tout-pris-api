import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from accounts.models import User
from catalog.base_catalog import BASE_ITEM_STATUSES, BASE_ITEM_TYPES
from catalog.models import Kit, KitItem
from households.models import Household, HouseholdMember, HouseholdRole, Person

pytestmark = pytest.mark.django_db


def household_snapshot():
    return {
        "households": list(
            Household.objects.values_list("name", "personal_of__email").order_by("name")
        ),
        "accounts": list(
            User.objects.values_list("username", "email", "first_name", "last_name").order_by(
                "username"
            )
        ),
        "memberships": list(
            HouseholdMember.objects.values_list("user__email", "role").order_by("user__email")
        ),
        "persons": list(Person.objects.values_list("name", "user__email").order_by("name")),
        "kits": list(
            Kit.objects.values_list("household__name", "name", "position").order_by(
                "household__name", "position"
            )
        ),
        "kit_lines": list(
            KitItem.objects.values_list(
                "kit__name", "item_type__name", "person__name", "quantity", "position"
            ).order_by("kit__name", "position")
        ),
    }


def test_seeding_creates_one_household_with_two_accounts_and_two_children():
    call_command("seed")

    household = Household.objects.get(personal_of=None)

    assert household.name == "Famille Martin"
    assert household.members.count() == 2
    assert household.persons.count() == 4
    assert list(household.persons.filter(user=None).values_list("name", flat=True)) == [
        "Jeanne",
        "Louis",
    ]


def test_seeded_accounts_carry_readable_names_and_own_the_household():
    call_command("seed")

    camille = User.objects.get(email="camille@example.com")

    shared = Household.objects.get(personal_of=None)

    assert camille.get_full_name() == "Camille Martin"
    assert camille.memberships.get(household=shared).role == HouseholdRole.OWNER
    assert camille.persons.get(household=shared).name == "Camille"
    assert not camille.has_usable_password()


def test_every_seeded_account_also_owns_a_personal_household():
    call_command("seed")

    for email in ["camille@example.com", "sacha@example.com"]:
        user = User.objects.get(email=email)
        personal = user.personal_household

        assert personal.members.count() == 1
        assert list(personal.persons.values_list("user__email", flat=True)) == [email]


def test_seeding_a_second_time_produces_the_same_data():
    call_command("seed")
    first_run = household_snapshot()
    Household.objects.all().delete()
    User.objects.all().delete()

    call_command("seed")

    assert household_snapshot() == first_run


def test_seeding_reports_what_it_created(capsys):
    call_command("seed")

    assert "Seeded Famille Martin with 2 accounts and 4 persons" in capsys.readouterr().out


@pytest.mark.django_db
def test_seeding_a_database_that_already_holds_a_household_is_refused():
    call_command("seed")

    with pytest.raises(CommandError):
        call_command("seed")


def test_every_seeded_household_starts_from_the_base_catalog():
    call_command("seed")

    for household in Household.objects.all():
        assert household.item_types.count() == len(BASE_ITEM_TYPES)
        assert household.item_statuses.count() == len(BASE_ITEM_STATUSES)


def test_the_shared_household_is_seeded_with_kits():
    call_command("seed")

    shared = Household.objects.get(personal_of=None)

    assert list(shared.kits.values_list("name", flat=True)) == [
        "Sac à langer",
        "Affaires de rando",
        "Affaires enfants",
    ]
    assert shared.kits.get(name="Sac à langer").items.count() == 4


def test_the_seeded_children_kit_repeats_its_lines_for_each_child():
    call_command("seed")

    children_kit = Kit.objects.get(name="Affaires enfants")

    assert list(children_kit.items.values_list("person__name", "item_type__name")) == [
        ("Jeanne", "T-shirt"),
        ("Jeanne", "Pantalon"),
        ("Jeanne", "Pyjama"),
        ("Jeanne", "Doudou"),
        ("Louis", "T-shirt"),
        ("Louis", "Pantalon"),
        ("Louis", "Pyjama"),
        ("Louis", "Doudou"),
    ]


def test_the_seeded_personal_households_hold_no_kit():
    call_command("seed")

    assert not Kit.objects.filter(household__personal_of__isnull=False).exists()
