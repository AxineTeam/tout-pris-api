from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower, Trim
from ordered_model.models import OrderedModelBase

from households.models import Household, Person


class ProgressCategory(models.TextChoices):
    NOT_STARTED = "not_started", "Not started"
    IN_PROGRESS = "in_progress", "In progress"
    DONE = "done", "Done"


class ItemType(models.Model):
    household = models.ForeignKey(
        Household,
        on_delete=models.CASCADE,
        related_name="item_types",
        help_text="Household owning this entry of the catalog, which is never shared.",
    )
    name = models.CharField(
        max_length=100,
        help_text="What the thing is called when picking it, such as bib or sandals.",
    )
    description = models.TextField(
        blank=True,
        help_text="Optional details telling apart two entries that share a name.",
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                "household",
                Lower(Trim("name")),
                name="unique_item_type_name_per_household",
            )
        ]

    def __str__(self):
        return self.name


class ItemStatus(OrderedModelBase):
    order_field_name = "position"
    order_with_respect_to = "household"

    household = models.ForeignKey(
        Household,
        on_delete=models.CASCADE,
        related_name="item_statuses",
        help_text="Household this preparation status belongs to, with its own wording.",
    )
    name = models.CharField(
        max_length=100,
        help_text="Wording shown on a line, such as taken out of the closet.",
    )
    color = models.CharField(
        max_length=7,
        validators=[RegexValidator(r"^#[0-9a-fA-F]{6}$", "Give a color as #rrggbb.")],
        help_text="Hexadecimal color the clients paint the status with, such as #f59e0b.",
    )
    progress = models.CharField(
        max_length=11,
        choices=ProgressCategory,
        default=ProgressCategory.NOT_STARTED,
        help_text="What the status counts as in the progress bar of a trip.",
    )
    position = models.PositiveIntegerField(
        editable=False,
        db_index=True,
        help_text="Rank in the household status list.",
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Whether a new line gets this status, true for one status of the household.",
    )

    class Meta:
        ordering = ["position"]
        verbose_name_plural = "item statuses"
        constraints = [
            models.UniqueConstraint(
                fields=["household"],
                condition=Q(is_default=True),
                name="unique_default_item_status_per_household",
            )
        ]

    def save(self, *args, **kwargs):
        if (
            self._state.adding
            and not ItemStatus.objects.filter(
                household_id=self.household_id, is_default=True
            ).exists()
        ):
            self.is_default = True
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Kit(OrderedModelBase):
    order_field_name = "position"
    order_with_respect_to = "household"

    household = models.ForeignKey(
        Household,
        on_delete=models.CASCADE,
        related_name="kits",
        help_text="Household this reusable block belongs to.",
    )
    name = models.CharField(
        max_length=100,
        help_text="What the block is called, such as diaper bag or hiking gear.",
    )
    description = models.TextField(
        blank=True,
        help_text="Optional reminder of what the block is meant to cover.",
    )
    position = models.PositiveIntegerField(
        editable=False,
        db_index=True,
        help_text="Rank of the section the kit displays as in a trip.",
    )

    class Meta:
        ordering = ["position"]

    def __str__(self):
        return self.name


class KitItem(OrderedModelBase):
    order_field_name = "position"
    order_with_respect_to = "kit"

    kit = models.ForeignKey(
        Kit,
        on_delete=models.CASCADE,
        related_name="items",
        help_text="Block this line belongs to, and outside of which it does not exist.",
    )
    item_type = models.ForeignKey(
        ItemType,
        on_delete=models.CASCADE,
        related_name="kit_items",
        help_text="Catalog entry the line packs, taken from the same household.",
    )
    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="kit_items",
        help_text="Person the line is for, empty when it is for the whole household.",
    )
    quantity = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(32767)],
        help_text="How many of the thing the block asks for, such as five t-shirts.",
    )
    note = models.CharField(
        max_length=200,
        blank=True,
        help_text="Free reminder carried to the trip, such as the warm one.",
    )
    position = models.PositiveIntegerField(
        editable=False,
        db_index=True,
        help_text="Rank in the block, which is the preparation order and follows into a trip.",
    )

    class Meta:
        ordering = ["position"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1),
                name="kit_item_quantity_is_at_least_one",
            )
        ]

    def __str__(self):
        return f"{self.quantity} {self.item_type}"
