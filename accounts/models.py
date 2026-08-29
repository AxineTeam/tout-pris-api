from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField(
        "email address",
        unique=True,
        help_text="Address the account signs in with, unique across the whole application.",
    )
    language = models.CharField(
        max_length=10,
        choices=settings.LANGUAGES,
        default=settings.LANGUAGE_CODE,
        help_text=(
            "Language the account is answered and written to in, whatever its browser asks for."
        ),
    )
