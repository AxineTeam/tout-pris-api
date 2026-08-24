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


@transaction.atomic
def rename_item_type(item_type, name):
    survivor = matching_item_type(item_type.household_id, name)
    if survivor is None or survivor.pk == item_type.pk:
        item_type.name = name
        item_type.save()
        return item_type
    item_type.kit_items.update(item_type=survivor)
    item_type.delete()
    return survivor
