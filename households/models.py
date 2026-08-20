from django.conf import settings
from django.db import models


class HouseholdRole(models.TextChoices):
    OWNER = "owner", "Owner"
    MEMBER = "member", "Member"


class Household(models.Model):
    name = models.CharField(
        max_length=100,
        help_text="Display name given by the members, such as their family name.",
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
