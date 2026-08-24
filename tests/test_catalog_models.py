import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from catalog.base_catalog import BASE_ITEM_STATUSES, BASE_ITEM_TYPES, install_base_catalog
from catalog.item_types import rename_item_type
from catalog.models import ItemStatus, ItemType, Kit, KitItem, ProgressCategory
from catalog.statuses import default_status, delete_status
from households.models import Household, Person
from tout_pris.exceptions import Conflict

pytestmark = pytest.mark.django_db


@pytest.fixture
def household():
    return Household.objects.create(name="Chez nous")


@pytest.fixture
def other_household():
    return Household.objects.create(name="Chez les grands-parents")


def make_status(household, name, progress=ProgressCategory.NOT_STARTED):
    return ItemStatus.objects.create(
        household=household, name=name, color="#94a3b8", progress=progress
    )


def test_an_item_type_is_named_after_its_name(household):
    assert str(ItemType.objects.create(household=household, name="Bavoir")) == "Bavoir"


def test_a_status_is_named_after_its_wording(household):
    assert str(make_status(household, "Dans les sacs")) == "Dans les sacs"


def test_a_kit_is_named_after_its_name(household):
    assert str(Kit.objects.create(household=household, name="Sac a langer")) == "Sac a langer"


def test_a_kit_line_reads_as_a_quantity_of_an_item_type(household):
    kit = Kit.objects.create(household=household, name="Sac a langer")
    item_type = ItemType.objects.create(household=household, name="Bavoir")

    line = KitItem.objects.create(kit=kit, item_type=item_type, quantity=2)

    assert str(line) == "2 Bavoir"


def test_two_item_types_differing_only_by_case_cannot_coexist(household):
    ItemType.objects.create(household=household, name="Chapeau")

    with pytest.raises(IntegrityError):
        ItemType.objects.create(household=household, name="chapeau")


def test_two_item_types_differing_only_by_surrounding_spaces_cannot_coexist(household):
    ItemType.objects.create(household=household, name="Chapeau")

    with pytest.raises(IntegrityError):
        ItemType.objects.create(household=household, name="  chapeau ")


def test_the_same_item_type_name_lives_in_two_households(household, other_household):
    ItemType.objects.create(household=household, name="Chapeau")
    ItemType.objects.create(household=other_household, name="Chapeau")

    assert ItemType.objects.filter(name="Chapeau").count() == 2


def test_renaming_an_item_type_to_a_free_name_keeps_it(household):
    item_type = ItemType.objects.create(household=household, name="Chapeaux")

    renamed = rename_item_type(item_type, "Chapeau")

    assert renamed.pk == item_type.pk
    assert ItemType.objects.get(pk=item_type.pk).name == "Chapeau"


def test_renaming_an_item_type_to_its_own_name_in_another_case_keeps_it(household):
    item_type = ItemType.objects.create(household=household, name="chapeau")

    renamed = rename_item_type(item_type, "Chapeau")

    assert renamed.pk == item_type.pk
    assert ItemType.objects.get(pk=item_type.pk).name == "Chapeau"


def test_renaming_an_item_type_to_a_taken_name_merges_it_into_the_survivor(household):
    survivor = ItemType.objects.create(household=household, name="Chapeau")
    absorbed = ItemType.objects.create(household=household, name="Chapeaux")
    kit = Kit.objects.create(household=household, name="Affaires de rando")
    line = KitItem.objects.create(kit=kit, item_type=absorbed, quantity=2)

    merged = rename_item_type(absorbed, "chapeau")

    line.refresh_from_db()

    assert merged.pk == survivor.pk
    assert line.item_type_id == survivor.pk
    assert not ItemType.objects.filter(pk=absorbed.pk).exists()


def test_renaming_an_item_type_ignores_a_namesake_of_another_household(household, other_household):
    ItemType.objects.create(household=other_household, name="Chapeau")
    item_type = ItemType.objects.create(household=household, name="Chapeaux")

    renamed = rename_item_type(item_type, "Chapeau")

    assert renamed.pk == item_type.pk


def test_statuses_are_numbered_in_creation_order_within_their_household(household):
    first = make_status(household, "Pas prepare")
    second = make_status(household, "Sorti du placard")

    assert [first.position, second.position] == [0, 1]


def test_status_positions_restart_in_another_household(household, other_household):
    make_status(household, "Pas prepare")

    elsewhere = make_status(other_household, "Pas prepare")

    assert elsewhere.position == 0


def test_deleting_a_status_closes_the_gap_it_leaves(household):
    make_status(household, "Pas prepare")
    dropped = make_status(household, "Commande en ligne", ProgressCategory.IN_PROGRESS)
    last = make_status(household, "Dans les sacs", ProgressCategory.DONE)

    dropped.delete()
    last.refresh_from_db()

    assert last.position == 1


def test_moving_a_status_up_swaps_it_with_its_neighbour(household):
    first = make_status(household, "Pas prepare")
    second = make_status(household, "Sorti du placard", ProgressCategory.IN_PROGRESS)

    second.up()
    first.refresh_from_db()

    assert [second.position, first.position] == [0, 1]


def test_kit_lines_are_numbered_within_their_kit(household):
    kit = Kit.objects.create(household=household, name="Sac a langer")
    other_kit = Kit.objects.create(household=household, name="Affaires de rando")
    item_type = ItemType.objects.create(household=household, name="Bavoir")

    first = KitItem.objects.create(kit=kit, item_type=item_type)
    second = KitItem.objects.create(kit=kit, item_type=item_type)
    elsewhere = KitItem.objects.create(kit=other_kit, item_type=item_type)

    assert [first.position, second.position, elsewhere.position] == [0, 1, 0]


def test_kits_are_numbered_within_their_household(household, other_household):
    first = Kit.objects.create(household=household, name="Sac a langer")
    second = Kit.objects.create(household=household, name="Affaires de rando")
    elsewhere = Kit.objects.create(household=other_household, name="Sac a langer")

    assert [first.position, second.position, elsewhere.position] == [0, 1, 0]


def test_a_kit_line_can_be_aimed_at_a_person(household):
    kit = Kit.objects.create(household=household, name="Affaires enfants")
    item_type = ItemType.objects.create(household=household, name="T-shirt")
    person = Person.objects.create(household=household, name="Enfant 1")

    line = KitItem.objects.create(kit=kit, item_type=item_type, person=person, quantity=5)

    assert person.kit_items.get() == line


def test_deleting_a_person_takes_away_the_lines_aimed_at_them(household):
    kit = Kit.objects.create(household=household, name="Affaires enfants")
    item_type = ItemType.objects.create(household=household, name="T-shirt")
    person = Person.objects.create(household=household, name="Enfant 1")
    KitItem.objects.create(kit=kit, item_type=item_type, person=person)

    person.delete()

    assert not KitItem.objects.exists()


def test_deleting_an_item_type_takes_away_the_kit_lines_packing_it(household):
    kit = Kit.objects.create(household=household, name="Sac a langer")
    item_type = ItemType.objects.create(household=household, name="Bavoir")
    KitItem.objects.create(kit=kit, item_type=item_type)

    item_type.delete()

    assert not KitItem.objects.exists()


def test_deleting_a_household_takes_away_its_catalog(household):
    install_base_catalog(household)
    kit = Kit.objects.create(household=household, name="Sac a langer")
    KitItem.objects.create(kit=kit, item_type=household.item_types.first())

    household.delete()

    assert not ItemType.objects.exists()
    assert not ItemStatus.objects.exists()
    assert not Kit.objects.exists()
    assert not KitItem.objects.exists()


def test_the_default_status_is_the_first_not_started_one(household):
    make_status(household, "Dans les sacs", ProgressCategory.DONE)
    expected = make_status(household, "Pas prepare")
    make_status(household, "A acheter sur place")

    assert default_status(household.pk) == expected


def test_a_household_without_any_not_started_status_has_no_default(household):
    make_status(household, "Dans les sacs", ProgressCategory.DONE)

    assert default_status(household.pk) is None


def test_deleting_the_last_not_started_status_is_refused(household):
    status = make_status(household, "Pas prepare")
    make_status(household, "Dans les sacs", ProgressCategory.DONE)

    with pytest.raises(Conflict):
        delete_status(status)

    assert ItemStatus.objects.filter(pk=status.pk).exists()


def test_deleting_the_default_status_hands_the_role_to_the_next_not_started_one(household):
    status = make_status(household, "Pas prepare")
    successor = make_status(household, "A acheter sur place")

    delete_status(status)

    assert default_status(household.pk) == successor


def test_deleting_a_status_that_is_not_the_last_not_started_one_is_allowed(household):
    make_status(household, "Pas prepare")
    status = make_status(household, "Dans les sacs", ProgressCategory.DONE)

    delete_status(status)

    assert not ItemStatus.objects.filter(pk=status.pk).exists()


def test_installing_the_base_catalog_fills_the_household(household):
    install_base_catalog(household)

    assert household.item_types.count() == len(BASE_ITEM_TYPES)
    assert list(household.item_statuses.values_list("name", "progress")) == [
        (name, progress) for name, _, progress in BASE_ITEM_STATUSES
    ]


def test_a_status_color_is_refused_unless_it_is_hexadecimal(household):
    status = ItemStatus(household=household, name="Commande en ligne", color="orange")

    with pytest.raises(ValidationError):
        status.full_clean()


def test_a_hexadecimal_status_color_is_accepted(household):
    ItemStatus(household=household, name="Commande en ligne", color="#f59e0b").full_clean()
