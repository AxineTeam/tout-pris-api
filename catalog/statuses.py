from django.db import transaction

from catalog.models import ItemStatus
from tout_pris.exceptions import Conflict


def default_status(household_id):
    return ItemStatus.objects.filter(household_id=household_id, is_default=True).first()


@transaction.atomic
def make_default(status):
    ItemStatus.objects.filter(household_id=status.household_id, is_default=True).update(
        is_default=False
    )
    status.is_default = True
    status.save()


@transaction.atomic
def delete_status(status):
    if status.is_default:
        raise Conflict(
            "The default status cannot be deleted, make another status the default one first."
        )
    siblings = (
        ItemStatus.objects.filter(household_id=status.household_id)
        .exclude(pk=status.pk)
        .order_by("position")
    )
    replacement = siblings.filter(progress=status.progress).first() or default_status(
        status.household_id
    )
    status.trip_items.update(status=replacement)
    status.delete()
