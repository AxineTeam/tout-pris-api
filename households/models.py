import datetime
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


class HouseholdRole(models.TextChoices):
    OWNER = "owner", "Owner"
    MEMBER = "member", "Member"


class Household(models.Model):
    name = models.CharField(
        max_length=100,
        help_text="Display name given by the members, such as their family name.",
    )
    personal_of = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="personal_household",
        help_text="Account this household is the private space of, empty when it is shared.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the household was created, usually at the first member's signup.",
    )

    def __str__(self):
        return self.name


class HouseholdMember(models.Model):
    household = models.ForeignKey(
        Household,
        on_delete=models.CASCADE,
        related_name="members",
        help_text="Household the membership grants access to.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
        help_text="Account granted access to the household, its people, its catalog and its trips.",
    )
    role = models.CharField(
        max_length=10,
        choices=HouseholdRole,
        default=HouseholdRole.MEMBER,
        help_text="Reserved for a later differentiation of rights: every member can do everything.",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["household", "user"], name="unique_membership_per_household"
            )
        ]


class Person(models.Model):
    household = models.ForeignKey(
        Household,
        on_delete=models.CASCADE,
        related_name="persons",
        help_text="Household the person belongs to, and outside of which they do not exist.",
    )
    name = models.CharField(
        max_length=100,
        help_text="Display name shown in every picker asking who an item is for.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="persons",
        help_text="Account of the person when they have one, empty for a child or a guest.",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["household", "user"], name="unique_account_person_per_household"
            )
        ]

    def __str__(self):
        return self.name


class Invitation(models.Model):
    LIFETIME = datetime.timedelta(days=7)

    household = models.ForeignKey(
        Household,
        on_delete=models.CASCADE,
        related_name="invitations",
        help_text="Shared household the invited address is offered membership of.",
    )
    email = models.EmailField(
        help_text="Address the invitation was sent to, which may or may not have an account.",
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        default=secrets.token_urlsafe,
        help_text="Opaque secret carried by the link, never a guessable identifier.",
    )
    person = models.ForeignKey(
        Person,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invitations",
        help_text="Person the guest is expected to be, so accepting fills that person in.",
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_invitations",
        help_text="Member who sent the invitation, emptied rather than cascading if they leave.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the invitation was created and its email sent.",
    )
    expires_at = models.DateTimeField(
        help_text="When the token stops being accepted, a week after it was created.",
    )
    accepted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the invitation was accepted, which spends the single-use token.",
    )
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accepted_invitations",
        help_text="Account that accepted the invitation, which is not always the invited address.",
    )

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + self.LIFETIME
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.email} to {self.household}"
