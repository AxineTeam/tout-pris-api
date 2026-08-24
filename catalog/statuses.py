from catalog.models import ItemStatus, ProgressCategory
from tout_pris.exceptions import Conflict


def default_status(household_id):
    return (
        ItemStatus.objects.filter(household_id=household_id, progress=ProgressCategory.NOT_STARTED)
        .order_by("position")
        .first()
    )


def delete_status(status):
    another_not_started = (
        ItemStatus.objects.filter(
            household_id=status.household_id, progress=ProgressCategory.NOT_STARTED
        )
        .exclude(pk=status.pk)
        .exists()
    )
    if not another_not_started:
        raise Conflict("The last not started status cannot be deleted, a new line would have none.")
    status.delete()
