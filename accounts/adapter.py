from allauth.account.adapter import DefaultAccountAdapter
from allauth.headless.adapter import DefaultHeadlessAdapter
from django.utils import translation

from accounts.models import User


class HeadlessAdapter(DefaultHeadlessAdapter):
    def serialize_user(self, user):
        return {**super().serialize_user(user), "language": user.language}


class AccountAdapter(DefaultAccountAdapter):
    def send_mail(self, template_prefix, email, context):
        with translation.override(language_written_to(email)):
            super().send_mail(template_prefix, email, context)


def language_written_to(email):
    account = User.objects.filter(email=email).first()
    return account.language if account else translation.get_language()
