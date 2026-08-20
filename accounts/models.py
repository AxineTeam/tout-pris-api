from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField(
        "email address",
        unique=True,
        help_text="Address the account signs in with, unique across the whole application.",
    )
