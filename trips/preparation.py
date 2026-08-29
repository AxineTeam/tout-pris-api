from django.db import transaction
from django.utils.translation import gettext_lazy as _

from catalog.statuses import default_status
from tout_pris.exceptions import Conflict
from trips.models import TripItem

NO_STATUS = _("A trip line needs a status, and this household has none to give it.")


def starting_status(household_id):
    status = default_status(household_id)
    if status is None:
        raise Conflict(NO_STATUS)
    return status


def packed_lines(trip):
    return set(trip.items.values_list("item_type_id", "person_id"))


@transaction.atomic
def instantiate_kit(trip, kit):
    status = starting_status(trip.household_id)
    participants = set(trip.participants.values_list("person_id", flat=True))
    already_packed = packed_lines(trip)
    created = []
    for line in kit.items.all():
        if line.person_id is not None and line.person_id not in participants:
            continue
        if (line.item_type_id, line.person_id) in already_packed:
            continue
        already_packed.add((line.item_type_id, line.person_id))
        created.append(
            TripItem.objects.create(
                trip=trip,
                item_type_id=line.item_type_id,
                person_id=line.person_id,
                quantity=line.quantity,
                note=line.note,
                status=status,
            )
        )
    return created
