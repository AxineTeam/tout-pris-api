import pytest
from django.test import Client

from accounts.models import User
from catalog import views as catalog_views
from catalog.base_catalog import DEFAULT_STATUS_COLOR
from catalog.item_types import matching_item_type
from catalog.models import ItemStatus, ItemType, Kit, KitItem, ProgressCategory
from households.models import Household, HouseholdMember, Person

pytestmark = pytest.mark.django_db


def item_types_url(household):
    return f"/api/households/{household.pk}/item-types/"


def item_type_url(household, item_type):
    return f"{item_types_url(household)}{item_type.pk}/"


def item_statuses_url(household):
    return f"/api/households/{household.pk}/item-statuses/"


def item_status_url(household, status):
    return f"{item_statuses_url(household)}{status.pk}/"


def signed_in(user):
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def camille():
    return User.objects.create_user(username="camille", email="camille@example.com")


@pytest.fixture
def household(camille):
    shared = Household.objects.create(name="Famille Martin")
    HouseholdMember.objects.create(household=shared, user=camille)
    Person.objects.create(household=shared, user=camille, name="Camille")
    return shared


@pytest.fixture
def client(camille):
    return signed_in(camille)


@pytest.fixture
def stranger_household():
    stranger = User.objects.create_user(username="sacha", email="sacha@example.com")
    other = Household.objects.create(name="Chez les autres")
    HouseholdMember.objects.create(household=other, user=stranger)
    return other


def blind_to_the_first_lookup(lookup):
    answered = []

    def blinded(household_id, name):
        if answered:
            return lookup(household_id, name)
        answered.append(name)
        return None

    return blinded


def make_status(household, name, progress=ProgressCategory.NOT_STARTED):
    return ItemStatus.objects.create(
        household=household, name=name, color="#94a3b8", progress=progress
    )


def test_the_item_types_of_a_household_are_listed_by_name(client, household):
    ItemType.objects.create(household=household, name="Chapeau")
    ItemType.objects.create(household=household, name="Bavoir")

    listed = client.get(item_types_url(household)).json()

    assert [item_type["name"] for item_type in listed] == ["Bavoir", "Chapeau"]


def test_creating_an_item_type_adds_it_to_the_catalog(client, household):
    response = client.post(
        item_types_url(household),
        {"name": "Bavoir", "description": "Le grand"},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Bavoir"
    assert household.item_types.filter(name="Bavoir", description="Le grand").exists()


def test_creating_an_item_type_already_in_the_catalog_returns_the_existing_one(client, household):
    existing = ItemType.objects.create(household=household, name="Chapeau", description="Le bob")

    response = client.post(
        item_types_url(household),
        {"name": " chapeau ", "description": "Un autre"},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {"id": existing.pk, "name": "Chapeau", "description": "Le bob"}
    assert household.item_types.count() == 1


def test_creating_an_item_type_twice_at_once_returns_the_one_that_won_the_race(
    client, household, monkeypatch
):
    existing = ItemType.objects.create(household=household, name="Chapeau", description="Le bob")
    monkeypatch.setattr(
        catalog_views, "matching_item_type", blind_to_the_first_lookup(matching_item_type)
    )

    response = client.post(
        item_types_url(household), {"name": "chapeau"}, content_type="application/json"
    )

    assert response.status_code == 200
    assert response.json() == {"id": existing.pk, "name": "Chapeau", "description": "Le bob"}
    assert household.item_types.count() == 1


def test_an_item_type_is_read_one_by_one(client, household):
    bavoir = ItemType.objects.create(household=household, name="Bavoir")

    response = client.get(item_type_url(household, bavoir))

    assert response.status_code == 200
    assert response.json() == {"id": bavoir.pk, "name": "Bavoir", "description": ""}


def test_renaming_an_item_type_to_a_free_name_keeps_its_identity(client, household):
    bavoir = ItemType.objects.create(household=household, name="Bavoir")

    response = client.patch(
        item_type_url(household, bavoir), {"name": "Bavoirs"}, content_type="application/json"
    )

    assert response.status_code == 200
    assert response.json() == {"id": bavoir.pk, "name": "Bavoirs", "description": ""}


def test_describing_an_item_type_leaves_its_name_alone(client, household):
    bavoir = ItemType.objects.create(household=household, name="Bavoir")

    response = client.patch(
        item_type_url(household, bavoir),
        {"description": "Le grand"},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {"id": bavoir.pk, "name": "Bavoir", "description": "Le grand"}


def test_renaming_an_item_type_to_a_taken_name_merges_it_into_the_survivor(client, household):
    survivor = ItemType.objects.create(household=household, name="Chapeau")
    absorbed = ItemType.objects.create(household=household, name="chapeaux")
    kit = Kit.objects.create(household=household, name="Sac a langer")
    line = KitItem.objects.create(kit=kit, item_type=absorbed, quantity=3)

    response = client.patch(
        item_type_url(household, absorbed), {"name": "Chapeau"}, content_type="application/json"
    )

    assert response.status_code == 200
    assert response.json()["id"] == survivor.pk
    assert not ItemType.objects.filter(pk=absorbed.pk).exists()
    line.refresh_from_db()
    assert line.item_type_id == survivor.pk


def test_a_merging_rename_leaves_the_survivor_description_alone(client, household):
    survivor = ItemType.objects.create(
        household=household, name="Chapeau", description="Tous les chapeaux"
    )
    absorbed = ItemType.objects.create(household=household, name="chapeaux")

    response = client.patch(
        item_type_url(household, absorbed),
        {"name": "Chapeau", "description": "Celui de paille"},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["description"] == "Tous les chapeaux"
    survivor.refresh_from_db()
    assert survivor.description == "Tous les chapeaux"


def test_an_item_type_is_deleted(client, household):
    bavoir = ItemType.objects.create(household=household, name="Bavoir")

    response = client.delete(item_type_url(household, bavoir))

    assert response.status_code == 204
    assert not ItemType.objects.filter(pk=bavoir.pk).exists()


def test_the_item_types_of_another_household_are_out_of_reach(client, stranger_household):
    theirs = ItemType.objects.create(household=stranger_household, name="Bavoir")

    assert client.get(item_types_url(stranger_household)).status_code == 404
    assert (
        client.post(
            item_types_url(stranger_household), {"name": "Bavoir"}, content_type="application/json"
        ).status_code
        == 404
    )
    assert client.get(item_type_url(stranger_household, theirs)).status_code == 404
    assert (
        client.patch(
            item_type_url(stranger_household, theirs),
            {"name": "Chapeau"},
            content_type="application/json",
        ).status_code
        == 404
    )
    assert client.delete(item_type_url(stranger_household, theirs)).status_code == 404


def test_an_item_type_of_another_household_is_unreachable_through_our_own(
    client, household, stranger_household
):
    theirs = ItemType.objects.create(household=stranger_household, name="Bavoir")

    assert client.get(item_type_url(household, theirs)).status_code == 404


def test_the_item_type_endpoints_refuse_an_unauthenticated_caller(household):
    anonymous = Client()

    assert anonymous.get(item_types_url(household)).status_code == 401
    assert anonymous.post(item_types_url(household), {"name": "Bavoir"}).status_code == 401


def test_the_statuses_of_a_household_are_listed_in_display_order(client, household):
    make_status(household, "Pas prepare")
    make_status(household, "Dans les sacs", ProgressCategory.DONE)

    listed = client.get(item_statuses_url(household)).json()

    assert [status["name"] for status in listed] == ["Pas prepare", "Dans les sacs"]
    assert [status["position"] for status in listed] == [0, 1]


def test_creating_a_status_appends_it_to_the_household_list(client, household):
    make_status(household, "Pas prepare")

    response = client.post(
        item_statuses_url(household),
        {"name": "Commande en ligne", "color": "#f59e0b", "progress": "in_progress"},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert response.json()["position"] == 1
    assert household.item_statuses.filter(name="Commande en ligne", color="#f59e0b").exists()


def test_a_status_created_without_a_color_gets_the_default_one(client, household):
    response = client.post(
        item_statuses_url(household), {"name": "A acheter"}, content_type="application/json"
    )

    assert response.status_code == 201
    assert response.json()["color"] == DEFAULT_STATUS_COLOR
    assert response.json()["progress"] == ProgressCategory.NOT_STARTED


def test_a_status_color_that_is_not_a_hexadecimal_one_is_refused(client, household):
    response = client.post(
        item_statuses_url(household),
        {"name": "A acheter", "color": "rouge"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not household.item_statuses.exists()


def test_a_status_is_read_one_by_one(client, household):
    status = make_status(household, "Pas prepare")

    response = client.get(item_status_url(household, status))

    assert response.status_code == 200
    assert response.json() == {
        "id": status.pk,
        "name": "Pas prepare",
        "color": "#94a3b8",
        "progress": "not_started",
        "position": 0,
        "is_default": True,
    }


def test_a_status_is_reworded_and_repainted(client, household):
    status = make_status(household, "Pas prepare")

    response = client.patch(
        item_status_url(household, status),
        {"name": "A preparer", "color": "#22c55e"},
        content_type="application/json",
    )

    assert response.status_code == 200
    status.refresh_from_db()
    assert (status.name, status.color) == ("A preparer", "#22c55e")


def test_a_status_that_is_not_the_default_one_is_deleted(client, household):
    make_status(household, "Pas prepare")
    spare = make_status(household, "A acheter sur place")

    response = client.delete(item_status_url(household, spare))

    assert response.status_code == 204
    assert not ItemStatus.objects.filter(pk=spare.pk).exists()


def test_the_default_status_is_not_deleted(client, household):
    only = make_status(household, "Pas prepare")
    make_status(household, "Dans les sacs", ProgressCategory.DONE)

    response = client.delete(item_status_url(household, only))

    assert response.status_code == 409
    assert ItemStatus.objects.filter(pk=only.pk).exists()


def test_the_default_status_is_deleted_once_another_one_took_the_role(client, household):
    former = make_status(household, "Pas prepare")
    successor = make_status(household, "A acheter sur place")

    client.patch(
        item_status_url(household, successor),
        {"is_default": True},
        content_type="application/json",
    )
    response = client.delete(item_status_url(household, former))

    assert response.status_code == 204
    assert not ItemStatus.objects.filter(pk=former.pk).exists()


def test_the_first_status_created_in_a_household_is_the_default_one(client, household):
    first = client.post(
        item_statuses_url(household), {"name": "Pas prepare"}, content_type="application/json"
    )
    second = client.post(
        item_statuses_url(household), {"name": "A acheter"}, content_type="application/json"
    )

    assert first.json()["is_default"] is True
    assert second.json()["is_default"] is False


def test_a_status_becomes_the_default_one_and_takes_the_role_from_the_previous_one(
    client, household
):
    previous = make_status(household, "Pas prepare")
    status = make_status(household, "A acheter sur place")

    response = client.patch(
        item_status_url(household, status),
        {"is_default": True},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["is_default"] is True
    status.refresh_from_db()
    previous.refresh_from_db()
    assert status.is_default
    assert not previous.is_default


def test_a_status_does_not_give_up_being_the_default_one(client, household):
    status = make_status(household, "Pas prepare")

    response = client.patch(
        item_status_url(household, status),
        {"is_default": False},
        content_type="application/json",
    )

    assert response.status_code == 400
    status.refresh_from_db()
    assert status.is_default


def test_the_statuses_of_another_household_are_out_of_reach(client, stranger_household):
    theirs = make_status(stranger_household, "Pas prepare")

    assert client.get(item_statuses_url(stranger_household)).status_code == 404
    assert (
        client.post(
            item_statuses_url(stranger_household),
            {"name": "Pas prepare"},
            content_type="application/json",
        ).status_code
        == 404
    )
    assert client.get(item_status_url(stranger_household, theirs)).status_code == 404
    assert (
        client.patch(
            item_status_url(stranger_household, theirs),
            {"name": "Autre"},
            content_type="application/json",
        ).status_code
        == 404
    )
    assert client.delete(item_status_url(stranger_household, theirs)).status_code == 404


def test_the_status_endpoints_refuse_an_unauthenticated_caller(household):
    anonymous = Client()

    assert anonymous.get(item_statuses_url(household)).status_code == 401
    assert anonymous.post(item_statuses_url(household), {"name": "Pas prepare"}).status_code == 401


def test_a_member_who_is_nobody_yet_reads_the_catalog_but_does_not_write_it(household):
    newcomer = User.objects.create_user(username="lou", email="lou@example.com")
    HouseholdMember.objects.create(household=household, user=newcomer)
    ItemType.objects.create(household=household, name="Bavoir")
    client = signed_in(newcomer)

    assert client.get(item_types_url(household)).status_code == 200
    assert (
        client.post(
            item_types_url(household), {"name": "Chapeau"}, content_type="application/json"
        ).status_code
        == 403
    )
    assert (
        client.post(
            item_statuses_url(household), {"name": "A acheter"}, content_type="application/json"
        ).status_code
        == 403
    )


def test_a_status_changes_progress_category(client, household):
    make_status(household, "Pas prepare")
    spare = make_status(household, "A acheter sur place")

    response = client.patch(
        item_status_url(household, spare),
        {"progress": ProgressCategory.IN_PROGRESS},
        content_type="application/json",
    )

    assert response.status_code == 200
    spare.refresh_from_db()
    assert spare.progress == ProgressCategory.IN_PROGRESS


def test_the_default_status_changes_progress_category_like_any_other(client, household):
    only = make_status(household, "Pas prepare")
    make_status(household, "Dans les sacs", ProgressCategory.DONE)

    response = client.patch(
        item_status_url(household, only),
        {"progress": ProgressCategory.DONE},
        content_type="application/json",
    )

    assert response.status_code == 200
    only.refresh_from_db()
    assert only.progress == ProgressCategory.DONE
    assert only.is_default


def test_a_status_is_deleted_in_a_household_that_started_with_none(client, household):
    client.post(
        item_statuses_url(household),
        {"name": "Dans les sacs", "progress": ProgressCategory.DONE},
        content_type="application/json",
    )
    spare = client.post(
        item_statuses_url(household),
        {"name": "Achete sur place", "progress": ProgressCategory.DONE},
        content_type="application/json",
    ).json()

    response = client.delete(f"{item_statuses_url(household)}{spare['id']}/")

    assert response.status_code == 204
    assert not ItemStatus.objects.filter(pk=spare["id"]).exists()


def test_a_status_moves_to_the_rank_it_is_given(client, household):
    make_status(household, "Pas prepare")
    make_status(household, "Sorti du placard")
    last = make_status(household, "Dans les sacs", ProgressCategory.DONE)

    response = client.patch(
        item_status_url(household, last), {"position": 0}, content_type="application/json"
    )

    assert response.status_code == 200
    assert response.json()["position"] == 0
    listed = client.get(item_statuses_url(household)).json()
    assert [status["name"] for status in listed] == [
        "Dans les sacs",
        "Pas prepare",
        "Sorti du placard",
    ]
    assert [status["position"] for status in listed] == [0, 1, 2]


def test_a_status_does_not_move_past_the_end_of_the_list(client, household):
    make_status(household, "Pas prepare")
    last = make_status(household, "Dans les sacs", ProgressCategory.DONE)

    response = client.patch(
        item_status_url(household, last), {"position": 2}, content_type="application/json"
    )

    assert response.status_code == 400
    last.refresh_from_db()
    assert last.position == 1


def test_a_status_does_not_move_before_the_head_of_the_list(client, household):
    make_status(household, "Pas prepare")
    last = make_status(household, "Dans les sacs", ProgressCategory.DONE)

    response = client.patch(
        item_status_url(household, last), {"position": -1}, content_type="application/json"
    )

    assert response.status_code == 400
    last.refresh_from_db()
    assert last.position == 1


def test_a_status_moves_within_its_own_household_list(client, household, stranger_household):
    make_status(stranger_household, "Pas prepare")
    make_status(stranger_household, "Sorti du placard")
    make_status(stranger_household, "Dans les sacs", ProgressCategory.DONE)
    mine = make_status(household, "Pas prepare")

    response = client.patch(
        item_status_url(household, mine), {"position": 2}, content_type="application/json"
    )

    assert response.status_code == 400
    mine.refresh_from_db()
    assert mine.position == 0
