from allauth.account.signals import user_signed_up
from django.db import transaction
from django.dispatch import receiver

from households.models import Household, HouseholdMember, HouseholdRole, Person


@receiver(user_signed_up)
@transaction.atomic
def create_household_for_new_account(sender, request, user, **kwargs):
    display_name = display_name_of(user)
    household = Household.objects.create(name=display_name, personal_of=user)
    HouseholdMember.objects.create(household=household, user=user, role=HouseholdRole.OWNER)
    Person.objects.create(household=household, user=user, name=display_name)


def display_name_of(user):
    return user.get_full_name().strip() or user.email.partition("@")[0]
