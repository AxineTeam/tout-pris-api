from allauth.account.signals import user_signed_up
from django.dispatch import receiver

from households.memberships import create_household, display_name_of


@receiver(user_signed_up)
def create_household_for_new_account(sender, request, user, **kwargs):
    create_household(display_name_of(user), user, personal_of=user)
