from allauth.account.signals import user_signed_up
from django.dispatch import receiver
from django.utils import translation


@receiver(user_signed_up)
def keep_the_language_the_signup_was_served_in(sender, request, user, **kwargs):
    user.language = translation.get_language()
    user.save(update_fields=["language"])
