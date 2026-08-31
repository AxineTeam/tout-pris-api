from django.db import transaction
from django.db.models import Value
from django.db.models.functions import Lower, Trim

from catalog.models import ItemType


def matching_item_type(household_id, name):
    return (
        ItemType.objects.filter(household_id=household_id)
        .annotate(normalized=Lower(Trim("name")))
        .filter(normalized=Lower(Trim(Value(name))))
        .first()
    )


def merge_trip_lines(absorbed, survivor):
    taken = set(survivor.trip_items.values_list("trip_id", "person_id"))
    for line in absorbed.trip_items.all():
        if (line.trip_id, line.person_id) in taken:
            line.delete()
        else:
            taken.add((line.trip_id, line.person_id))
            line.item_type = survivor
            line.save(update_fields=["item_type", "updated_at"])


@transaction.atomic
def rename_item_type(item_type, name):
    survivor = matching_item_type(item_type.household_id, name)
    if survivor is None or survivor.pk == item_type.pk:
        item_type.name = name
        item_type.save()
        return item_type
    item_type.kit_items.update(item_type=survivor)
    merge_trip_lines(item_type, survivor)
    item_type.delete()
    return survivor
