from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from model_bakery import baker

from accounts.models import User
from catalog.base_catalog import install_base_catalog
from households.models import Household, HouseholdMember, HouseholdRole, Person

RANDOM_SEED = 0
HOUSEHOLD_NAME = "Famille Martin"
ACCOUNTS = [
    ("Camille", "Martin", HouseholdRole.OWNER),
    ("Sacha", "Martin", HouseholdRole.MEMBER),
]
CHILDREN = ["Jeanne", "Louis"]


class Command(BaseCommand):
    help = "Fill the database with one household, two accounts and two children without account"

    @transaction.atomic
    def handle(self, *args, **options):
        if Household.objects.exists():
            raise CommandError(
                "The database already holds a household, run reset_db and migrate first"
            )

        baker.seed(RANDOM_SEED)
        household = baker.make(Household, name=HOUSEHOLD_NAME)
        install_base_catalog(household)
        for first_name, last_name, role in ACCOUNTS:
            user = baker.make(
                User,
                username=first_name.lower(),
                email=f"{first_name.lower()}@example.com",
                first_name=first_name,
                last_name=last_name,
            )
            user.set_unusable_password()
            user.save()
            baker.make(HouseholdMember, household=household, user=user, role=role)
            baker.make(Person, household=household, user=user, name=first_name)
            personal = baker.make(Household, name=first_name, personal_of=user)
            install_base_catalog(personal)
            baker.make(HouseholdMember, household=personal, user=user, role=HouseholdRole.OWNER)
            baker.make(Person, household=personal, user=user, name=first_name)
        for name in CHILDREN:
            baker.make(Person, household=household, name=name)
        self.stdout.write(
            f"Seeded {household.name} with {household.members.count()} accounts "
            f"and {household.persons.count()} persons, "
            f"each account holding its own personal household, "
            f"every household starting from the base catalog "
            f"of {household.item_types.count()} objects "
            f"and {household.item_statuses.count()} statuses"
        )
