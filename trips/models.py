from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from ordered_model.models import OrderedModelBase

from catalog.models import ItemStatus, ItemType
from households.models import Household, Person


class Trip(models.Model):
    household = models.ForeignKey(
        Household,
        on_delete=models.CASCADE,
        related_name="trips",
        help_text="Household preparing the trip, whose members share the same list.",
    )
    name = models.CharField(
        max_length=100,
        help_text="What the trip is called, such as a week in Brittany.",
    )
    date = models.DateField(
        help_text="Day the trip leaves on, which the trip list is sorted on.",
    )
    archived_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When the trip left the current list, empty as long as it is still there.",
    )

    class Meta:
        ordering = ["-date", "-pk"]

    def __str__(self):
        return self.name


class TripParticipant(models.Model):
    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name="participants",
        help_text="Trip the person is going on.",
    )
    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        related_name="trip_participations",
        help_text="Person going on the trip, whose kit lines are the ones instantiated.",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["trip", "person"], name="unique_participant_per_trip")
        ]


class TripItem(OrderedModelBase):
    order_field_name = "position"
    order_with_respect_to = "trip"

    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name="items",
        help_text="Trip this line belongs to, and outside of which it does not exist.",
    )
    item_type = models.ForeignKey(
        ItemType,
        on_delete=models.CASCADE,
        related_name="trip_items",
        help_text="Catalog entry the line packs, taken from the same household.",
    )
    person = models.ForeignKey(
        Person,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trip_items",
        help_text="Person the line is for, empty when the thing is common or the person is gone.",
    )
    quantity = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(32767)],
        help_text="How many of the thing to pack, such as five t-shirts.",
    )
    status = models.ForeignKey(
        ItemStatus,
        on_delete=models.RESTRICT,
        related_name="trip_items",
        help_text="Where the preparation of the line stands, which any member moves forward.",
    )
    note = models.CharField(
        max_length=200,
        blank=True,
        help_text="Free reminder shown on the line, such as the warm one.",
    )
    position = models.PositiveIntegerField(
        editable=False,
        db_index=True,
        help_text="Rank in the trip, taken from the kit at instantiation and editable afterwards.",
    )

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["trip", "item_type", "person"], name="unique_trip_line_per_person"
            ),
            models.UniqueConstraint(
                fields=["trip", "item_type"],
                condition=models.Q(person__isnull=True),
                name="unique_common_trip_line",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1),
                name="trip_item_quantity_is_at_least_one",
            ),
        ]

    def __str__(self):
        return f"{self.quantity} {self.item_type}"
