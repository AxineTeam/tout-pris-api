from django.db import transaction

from households.models import Household, HouseholdMember, HouseholdRole, Person


def display_name_of(user):
    return user.get_full_name().strip() or user.email.partition("@")[0]


@transaction.atomic
def create_household(name, owner, personal_of=None):
    household = Household.objects.create(name=name, personal_of=personal_of)
    HouseholdMember.objects.create(household=household, user=owner, role=HouseholdRole.OWNER)
    Person.objects.create(household=household, user=owner, name=display_name_of(owner))
    return household


@transaction.atomic
def remove_member(member):
    Person.objects.filter(household=member.household_id, user=member.user_id).update(user=None)
    member.delete()
