from django.core.management.base import BaseCommand, CommandError
from django.db.models import Exists, F, OuterRef, Q

from accounts.models import User
from catalog.models import ItemStatus, KitItem, ProgressCategory
from households.models import Household, HouseholdMember, Person


def accounts_without_a_personal_household():
    return [
        f"#{user.pk} {user.email}"
        for user in User.objects.filter(
            personal_household__isnull=True, is_staff=False, is_superuser=False
        ).order_by("pk")
    ]


def shared_households_without_a_member():
    return [
        f"#{household.pk} {household.name}"
        for household in Household.objects.filter(
            personal_of__isnull=True, members__isnull=True
        ).order_by("pk")
    ]


def persons_whose_account_is_not_a_member():
    membership = HouseholdMember.objects.filter(
        household=OuterRef("household"), user=OuterRef("user")
    )
    return [
        f"#{person.pk} {person.name} of household #{person.household_id}, {person.user.email}"
        for person in Person.objects.filter(user__isnull=False)
        .exclude(Exists(membership))
        .select_related("user")
        .order_by("pk")
    ]


def kit_lines_reaching_outside_their_household():
    foreign_item_type = ~Q(item_type__household=F("kit__household"))
    foreign_person = Q(person__isnull=False) & ~Q(person__household=F("kit__household"))
    return [
        f"#{line.pk} {line.item_type.name} in kit #{line.kit_id} "
        f"of household #{line.kit.household_id}"
        for line in KitItem.objects.filter(foreign_item_type | foreign_person)
        .select_related("item_type", "kit")
        .order_by("pk")
    ]


def households_whose_statuses_have_no_starting_point():
    not_started = ItemStatus.objects.filter(
        household=OuterRef("pk"), progress=ProgressCategory.NOT_STARTED
    )
    return [
        f"#{household.pk} {household.name}"
        for household in Household.objects.filter(item_statuses__isnull=False)
        .exclude(Exists(not_started))
        .distinct()
        .order_by("pk")
    ]


INVARIANTS = [
    ("Accounts without a personal household", accounts_without_a_personal_household),
    ("Shared households without a member", shared_households_without_a_member),
    (
        "Persons whose account is not a member of their household",
        persons_whose_account_is_not_a_member,
    ),
    (
        "Kit lines whose item type or person belongs to another household",
        kit_lines_reaching_outside_their_household,
    ),
    (
        "Households whose statuses hold no not started one",
        households_whose_statuses_have_no_starting_point,
    ),
]


class Command(BaseCommand):
    help = "List the states the model forbids but the schema cannot prevent"

    def handle(self, *args, **options):
        found = 0
        for title, forbidden_state in INVARIANTS:
            listed = forbidden_state()
            if not listed:
                continue
            found += len(listed)
            self.stdout.write(title)
            for line in listed:
                self.stdout.write(f"  {line}")
        if found:
            raise CommandError(f"{found} forbidden states found")
