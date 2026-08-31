import datetime

import pytest
from django.test import Client
from django.utils import timezone

from accounts.models import User
from catalog.models import ItemStatus, ItemType, Kit, KitItem
from households.models import Household, HouseholdMember, Person
from trips import preparation as trips_preparation
from trips.models import Trip, TripItem, TripParticipant
from trips.preparation import packed_lines

pytestmark = pytest.mark.django_db

READING_A_TRIP_LIST_OF_LINES = 7


def trips_url(household):
    return f"/api/households/{household.pk}/trips/"


def trip_url(household, trip):
    return f"{trips_url(household)}{trip.pk}/"


def participants_url(household, trip):
    return f"{trip_url(household, trip)}participants/"


def participant_url(household, trip, participant):
    return f"{participants_url(household, trip)}{participant.pk}/"


def items_url(household, trip):
    return f"{trip_url(household, trip)}items/"


def item_url(household, trip, line):
    return f"{items_url(household, trip)}{line.pk}/"


def kits_url(household, trip):
    return f"{trip_url(household, trip)}kits/"


def duplicate_url(household, trip):
    return f"{trip_url(household, trip)}duplicate/"


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


@pytest.fixture
def to_pack(household):
    return ItemStatus.objects.create(household=household, name="A preparer", color="#7b8189")


@pytest.fixture
def packed(household, to_pack):
    return ItemStatus.objects.create(household=household, name="Dans les sacs", color="#22c55e")


@pytest.fixture
def trip(household):
    return Trip.objects.create(household=household, name="Bretagne", date="2026-07-14")


@pytest.fixture
def leo(household):
    return Person.objects.create(household=household, name="Leo")


@pytest.fixture
def tshirt(household):
    return ItemType.objects.create(household=household, name="T-shirt")


@pytest.fixture
def rando(household):
    return Kit.objects.create(household=household, name="Affaires de rando")


def blind_to_the_first_reading(reading):
    answered = []

    def blinded(trip):
        if answered:
            return reading(trip)
        answered.append(trip)
        return set()

    return blinded


def test_the_trips_of_a_household_are_listed_from_the_next_departure_backwards(client, household):
    Trip.objects.create(household=household, name="Noel", date="2025-12-24")
    Trip.objects.create(household=household, name="Bretagne", date="2026-07-14")

    listed = client.get(trips_url(household)).json()

    assert [entry["name"] for entry in listed] == ["Bretagne", "Noel"]
    assert listed[0]["date"] == "2026-07-14"


def test_the_trip_list_carries_neither_the_participants_nor_the_lines(
    client, household, trip, tshirt, to_pack
):
    TripItem.objects.create(trip=trip, item_type=tshirt, status=to_pack)

    listed = client.get(trips_url(household)).json()

    assert listed == [
        {"id": trip.pk, "name": "Bretagne", "date": "2026-07-14", "archived_at": None}
    ]


def test_creating_a_trip_names_it_and_dates_its_departure(client, household):
    response = client.post(
        trips_url(household),
        {"name": "Bretagne", "date": "2026-07-14"},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Bretagne"
    assert household.trips.filter(name="Bretagne", date="2026-07-14").exists()


def test_a_trip_without_a_departure_date_is_refused(client, household):
    response = client.post(
        trips_url(household), {"name": "Bretagne"}, content_type="application/json"
    )

    assert response.status_code == 400
    assert not household.trips.exists()


def test_a_trip_is_read_with_its_participants_and_its_lines_in_preparation_order(
    client, household, trip, leo, tshirt, to_pack, rando
):
    TripParticipant.objects.create(trip=trip, person=leo)
    KitItem.objects.create(kit=rando, item_type=tshirt)
    line = TripItem.objects.create(
        trip=trip, item_type=tshirt, person=leo, quantity=5, status=to_pack
    )
    TripItem.objects.create(
        trip=trip,
        item_type=ItemType.objects.create(household=household, name="Creme solaire"),
        status=to_pack,
    )

    response = client.get(trip_url(household, trip))

    assert response.status_code == 200
    body = response.json()
    assert body["participants"] == [
        {"id": trip.participants.get().pk, "person": {"id": leo.pk, "name": "Leo", "user": None}}
    ]
    assert body["items"][0] == {
        "id": line.pk,
        "item_type": {"id": tshirt.pk, "name": "T-shirt", "description": ""},
        "person": {"id": leo.pk, "name": "Leo", "user": None},
        "quantity": 5,
        "status": {
            "id": to_pack.pk,
            "name": "A preparer",
            "color": "#7b8189",
            "progress": "not_started",
            "position": 0,
            "is_default": True,
        },
        "position": 0,
        "kits": [{"id": rando.pk, "name": "Affaires de rando", "description": "", "position": 0}],
    }
    assert body["items"][1]["kits"] == []
    assert [entry["position"] for entry in body["items"]] == [0, 1]


def test_a_trip_is_renamed_and_moved_to_another_date(client, household, trip):
    response = client.patch(
        trip_url(household, trip),
        {"name": "Bretagne en aout", "date": "2026-08-01"},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["items"] == []
    trip.refresh_from_db()
    assert (trip.name, str(trip.date)) == ("Bretagne en aout", "2026-08-01")


def test_archiving_a_trip_takes_it_out_of_the_current_list(client, household, trip):
    response = client.patch(
        trip_url(household, trip), {"archived": True}, content_type="application/json"
    )

    assert response.status_code == 200
    assert response.json()["archived_at"] is not None
    trip.refresh_from_db()
    assert trip.archived_at is not None
    assert client.get(trips_url(household)).json() == []


def test_the_archived_trips_are_listed_on_demand_from_the_last_archived(client, household):
    Trip.objects.create(
        household=household,
        name="Bretagne",
        date="2026-07-14",
        archived_at=datetime.datetime(2026, 8, 1, tzinfo=datetime.UTC),
    )
    Trip.objects.create(
        household=household,
        name="Noel",
        date="2025-12-24",
        archived_at=datetime.datetime(2026, 8, 2, tzinfo=datetime.UTC),
    )
    Trip.objects.create(household=household, name="Corse", date="2026-09-01")

    listed = client.get(trips_url(household), {"archived": "true"}).json()

    assert [entry["name"] for entry in listed] == ["Noel", "Bretagne"]


def test_unarchiving_a_trip_brings_it_back_to_the_current_list(client, household, trip):
    trip.archived_at = timezone.now()
    trip.save()

    response = client.patch(
        trip_url(household, trip), {"archived": False}, content_type="application/json"
    )

    assert response.status_code == 200
    assert response.json()["archived_at"] is None
    assert [entry["name"] for entry in client.get(trips_url(household)).json()] == ["Bretagne"]
    assert client.get(trips_url(household), {"archived": "true"}).json() == []


def test_the_day_a_trip_was_archived_is_not_for_the_client_to_choose(client, household, trip):
    response = client.patch(
        trip_url(household, trip),
        {"archived_at": "2020-01-01T00:00:00Z"},
        content_type="application/json",
    )

    assert response.status_code == 200
    trip.refresh_from_db()
    assert trip.archived_at is None


def test_an_archived_trip_still_takes_every_write(client, household, trip, leo, tshirt, to_pack):
    client.patch(trip_url(household, trip), {"archived": True}, content_type="application/json")

    added = client.post(
        items_url(household, trip), {"item_type": tshirt.pk}, content_type="application/json"
    )
    joined = client.post(
        participants_url(household, trip), {"person": leo.pk}, content_type="application/json"
    )
    renamed = client.patch(
        trip_url(household, trip), {"name": "Bretagne en aout"}, content_type="application/json"
    )
    moved = client.patch(
        item_url(household, trip, trip.items.get()),
        {"quantity": 2},
        content_type="application/json",
    )

    assert [added.status_code, joined.status_code] == [201, 201]
    assert [renamed.status_code, moved.status_code] == [200, 200]


def test_deleting_a_trip_takes_its_participants_and_its_lines_with_it(
    client, household, trip, leo, tshirt, to_pack
):
    participant = TripParticipant.objects.create(trip=trip, person=leo)
    line = TripItem.objects.create(trip=trip, item_type=tshirt, status=to_pack)

    response = client.delete(trip_url(household, trip))

    assert response.status_code == 204
    assert not Trip.objects.filter(pk=trip.pk).exists()
    assert not TripParticipant.objects.filter(pk=participant.pk).exists()
    assert not TripItem.objects.filter(pk=line.pk).exists()


def test_the_trips_of_another_household_are_out_of_reach(client, stranger_household):
    theirs = Trip.objects.create(household=stranger_household, name="Le leur", date="2026-07-14")

    assert client.get(trips_url(stranger_household)).status_code == 404
    assert (
        client.post(
            trips_url(stranger_household),
            {"name": "Le mien", "date": "2026-07-14"},
            content_type="application/json",
        ).status_code
        == 404
    )
    assert client.get(trip_url(stranger_household, theirs)).status_code == 404
    assert (
        client.patch(
            trip_url(stranger_household, theirs),
            {"name": "Le mien"},
            content_type="application/json",
        ).status_code
        == 404
    )
    assert client.delete(trip_url(stranger_household, theirs)).status_code == 404


def test_a_trip_of_another_household_is_unreachable_through_our_own(
    client, household, stranger_household
):
    theirs = Trip.objects.create(household=stranger_household, name="Le leur", date="2026-07-14")

    assert client.get(trip_url(household, theirs)).status_code == 404
    assert client.get(items_url(household, theirs)).status_code == 404
    assert client.get(participants_url(household, theirs)).status_code == 404


def test_the_trip_endpoints_refuse_an_unauthenticated_caller(household, trip):
    anonymous = Client()

    assert anonymous.get(trips_url(household)).status_code == 401
    assert anonymous.get(items_url(household, trip)).status_code == 401
    assert anonymous.post(kits_url(household, trip), {"kit": 1}).status_code == 401


def test_a_member_who_is_nobody_yet_reads_the_trips_but_does_not_prepare_them(
    household, trip, tshirt, to_pack
):
    newcomer = User.objects.create_user(username="lou", email="lou@example.com")
    HouseholdMember.objects.create(household=household, user=newcomer)
    client = signed_in(newcomer)

    assert client.get(trips_url(household)).status_code == 200
    assert client.get(items_url(household, trip)).status_code == 200
    assert (
        client.post(
            trips_url(household),
            {"name": "Le mien", "date": "2026-07-14"},
            content_type="application/json",
        ).status_code
        == 403
    )
    assert (
        client.post(
            items_url(household, trip),
            {"item_type": tshirt.pk},
            content_type="application/json",
        ).status_code
        == 403
    )
    assert (
        client.post(
            duplicate_url(household, trip),
            {"name": "Le mien", "date": "2027-07-14"},
            content_type="application/json",
        ).status_code
        == 403
    )


def test_the_people_going_on_a_trip_are_listed_and_added(client, household, trip, leo):
    response = client.post(
        participants_url(household, trip), {"person": leo.pk}, content_type="application/json"
    )

    assert response.status_code == 201
    assert response.json()["person"] == {"id": leo.pk, "name": "Leo", "user": None}
    listed = client.get(participants_url(household, trip)).json()
    assert [entry["person"]["name"] for entry in listed] == ["Leo"]


def test_someone_already_going_on_a_trip_is_not_added_twice(client, household, trip, leo):
    client.post(
        participants_url(household, trip), {"person": leo.pk}, content_type="application/json"
    )

    response = client.post(
        participants_url(household, trip), {"person": leo.pk}, content_type="application/json"
    )

    assert response.status_code == 409
    assert trip.participants.count() == 1


def test_removing_someone_from_a_trip_leaves_what_was_prepared_for_them(
    client, household, trip, leo, tshirt, to_pack
):
    participant = TripParticipant.objects.create(trip=trip, person=leo)
    line = TripItem.objects.create(trip=trip, item_type=tshirt, person=leo, status=to_pack)

    response = client.delete(participant_url(household, trip, participant))

    assert response.status_code == 204
    assert not trip.participants.exists()
    assert TripItem.objects.filter(pk=line.pk, person=leo).exists()


def test_a_trip_cannot_take_along_someone_of_another_household(
    client, household, trip, stranger_household
):
    theirs = Person.objects.create(household=stranger_household, name="Sacha")

    response = client.post(
        participants_url(household, trip), {"person": theirs.pk}, content_type="application/json"
    )

    assert response.status_code == 404
    assert not trip.participants.exists()


def test_the_participants_of_a_trip_of_another_household_are_out_of_reach(
    client, stranger_household, leo
):
    theirs = Trip.objects.create(household=stranger_household, name="Le leur", date="2026-07-14")
    participant = TripParticipant.objects.create(
        trip=theirs, person=Person.objects.create(household=stranger_household, name="Sacha")
    )

    assert client.get(participants_url(stranger_household, theirs)).status_code == 404
    assert (
        client.post(
            participants_url(stranger_household, theirs),
            {"person": leo.pk},
            content_type="application/json",
        ).status_code
        == 404
    )
    removed = client.delete(participant_url(stranger_household, theirs, participant))
    assert removed.status_code == 404


def test_a_line_added_by_hand_starts_on_the_default_status_of_the_household(
    client, household, trip, tshirt, to_pack
):
    response = client.post(
        items_url(household, trip), {"item_type": tshirt.pk}, content_type="application/json"
    )

    assert response.status_code == 201
    assert response.json()["status"]["id"] == to_pack.pk
    assert response.json()["quantity"] == 1
    assert response.json()["person"] is None
    assert response.json()["kits"] == []


def test_a_line_is_added_on_a_chosen_status_for_a_chosen_person(
    client, household, trip, leo, tshirt, to_pack, packed
):
    response = client.post(
        items_url(household, trip),
        {
            "item_type": tshirt.pk,
            "person": leo.pk,
            "quantity": 5,
            "status": packed.pk,
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    assert response.json()["status"]["name"] == "Dans les sacs"
    assert trip.items.filter(person=leo, quantity=5, status=packed).exists()


def test_a_line_cannot_be_added_to_a_household_that_has_no_status_yet(
    client, household, trip, tshirt
):
    response = client.post(
        items_url(household, trip), {"item_type": tshirt.pk}, content_type="application/json"
    )

    assert response.status_code == 409
    assert not trip.items.exists()


def test_the_same_object_does_not_enter_a_trip_twice_for_the_same_person(
    client, household, trip, tshirt, to_pack
):
    client.post(
        items_url(household, trip), {"item_type": tshirt.pk}, content_type="application/json"
    )

    response = client.post(
        items_url(household, trip), {"item_type": tshirt.pk}, content_type="application/json"
    )

    assert response.status_code == 409
    assert trip.items.count() == 1


def test_a_line_that_would_collide_with_another_one_is_refused(
    client, household, trip, leo, tshirt, to_pack
):
    TripItem.objects.create(trip=trip, item_type=tshirt, person=leo, status=to_pack)
    line = TripItem.objects.create(trip=trip, item_type=tshirt, status=to_pack)

    response = client.patch(
        item_url(household, trip, line), {"person": leo.pk}, content_type="application/json"
    )

    assert response.status_code == 409
    line.refresh_from_db()
    assert line.person_id is None


def test_the_lines_of_a_trip_are_listed_in_preparation_order(
    client, household, trip, tshirt, to_pack
):
    TripItem.objects.create(trip=trip, item_type=tshirt, quantity=5, status=to_pack)
    TripItem.objects.create(
        trip=trip,
        item_type=ItemType.objects.create(household=household, name="Creme solaire"),
        quantity=1,
        status=to_pack,
    )

    listed = client.get(items_url(household, trip)).json()

    assert [entry["quantity"] for entry in listed] == [5, 1]
    assert [entry["position"] for entry in listed] == [0, 1]


def test_a_line_is_read_one_by_one(client, household, trip, tshirt, to_pack):
    line = TripItem.objects.create(trip=trip, item_type=tshirt, quantity=3, status=to_pack)

    response = client.get(item_url(household, trip, line))

    assert response.status_code == 200
    assert response.json()["quantity"] == 3
    assert response.json()["kits"] == []


def test_a_line_moves_forward_and_changes_its_quantity_its_object_and_its_person(
    client, household, trip, leo, tshirt, to_pack, packed
):
    line = TripItem.objects.create(trip=trip, item_type=tshirt, quantity=5, status=to_pack)
    creme = ItemType.objects.create(household=household, name="Creme solaire")

    response = client.patch(
        item_url(household, trip, line),
        {
            "item_type": creme.pk,
            "person": leo.pk,
            "quantity": 3,
            "status": packed.pk,
        },
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["status"]["name"] == "Dans les sacs"
    line.refresh_from_db()
    assert (line.item_type_id, line.person_id, line.quantity) == (creme.pk, leo.pk, 3)


def test_a_line_packs_at_least_one_of_something(client, household, trip, tshirt, to_pack):
    line = TripItem.objects.create(trip=trip, item_type=tshirt, quantity=3, status=to_pack)

    response = client.patch(
        item_url(household, trip, line), {"quantity": 0}, content_type="application/json"
    )

    assert response.status_code == 400
    line.refresh_from_db()
    assert line.quantity == 3


def test_a_line_packs_no_more_than_a_small_integer_holds(client, household, trip, tshirt, to_pack):
    response = client.post(
        items_url(household, trip),
        {"item_type": tshirt.pk, "quantity": 40000},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not trip.items.exists()


def test_a_line_aimed_at_someone_becomes_common_again(
    client, household, trip, leo, tshirt, to_pack
):
    line = TripItem.objects.create(trip=trip, item_type=tshirt, person=leo, status=to_pack)

    response = client.patch(
        item_url(household, trip, line), {"person": None}, content_type="application/json"
    )

    assert response.status_code == 200
    assert response.json()["person"] is None
    line.refresh_from_db()
    assert line.person_id is None


def test_a_line_that_drops_its_status_is_refused(client, household, trip, tshirt, to_pack):
    line = TripItem.objects.create(trip=trip, item_type=tshirt, status=to_pack)

    response = client.patch(
        item_url(household, trip, line), {"status": None}, content_type="application/json"
    )

    assert response.status_code == 400
    line.refresh_from_db()
    assert line.status_id == to_pack.pk


def test_a_line_is_deleted(client, household, trip, tshirt, to_pack):
    line = TripItem.objects.create(trip=trip, item_type=tshirt, status=to_pack)

    response = client.delete(item_url(household, trip, line))

    assert response.status_code == 204
    assert not TripItem.objects.filter(pk=line.pk).exists()


def test_a_line_cannot_pack_an_object_of_another_household(
    client, household, trip, tshirt, to_pack, stranger_household
):
    theirs = ItemType.objects.create(household=stranger_household, name="Le leur")
    line = TripItem.objects.create(trip=trip, item_type=tshirt, status=to_pack)

    created = client.post(
        items_url(household, trip), {"item_type": theirs.pk}, content_type="application/json"
    )
    patched = client.patch(
        item_url(household, trip, line), {"item_type": theirs.pk}, content_type="application/json"
    )

    assert (created.status_code, patched.status_code) == (404, 404)
    assert trip.items.count() == 1
    line.refresh_from_db()
    assert line.item_type_id == tshirt.pk


def test_a_line_cannot_aim_at_a_person_of_another_household(
    client, household, trip, tshirt, to_pack, stranger_household
):
    theirs = Person.objects.create(household=stranger_household, name="Sacha")
    line = TripItem.objects.create(trip=trip, item_type=tshirt, status=to_pack)

    created = client.post(
        items_url(household, trip),
        {"item_type": tshirt.pk, "person": theirs.pk},
        content_type="application/json",
    )
    patched = client.patch(
        item_url(household, trip, line), {"person": theirs.pk}, content_type="application/json"
    )

    assert (created.status_code, patched.status_code) == (404, 404)
    assert trip.items.count() == 1
    line.refresh_from_db()
    assert line.person_id is None


def test_a_line_cannot_take_a_status_of_another_household(
    client, household, trip, tshirt, to_pack, stranger_household
):
    theirs = ItemStatus.objects.create(
        household=stranger_household, name="Le leur", color="#7b8189"
    )
    line = TripItem.objects.create(trip=trip, item_type=tshirt, status=to_pack)

    created = client.post(
        items_url(household, trip),
        {"item_type": tshirt.pk, "status": theirs.pk},
        content_type="application/json",
    )
    patched = client.patch(
        item_url(household, trip, line), {"status": theirs.pk}, content_type="application/json"
    )

    assert (created.status_code, patched.status_code) == (404, 404)
    assert trip.items.count() == 1
    line.refresh_from_db()
    assert line.status_id == to_pack.pk


def test_the_lines_of_a_trip_of_another_household_are_out_of_reach(
    client, stranger_household, tshirt
):
    theirs = Trip.objects.create(household=stranger_household, name="Le leur", date="2026-07-14")
    line = TripItem.objects.create(
        trip=theirs,
        item_type=ItemType.objects.create(household=stranger_household, name="Le leur"),
        status=ItemStatus.objects.create(
            household=stranger_household, name="Le leur", color="#7b8189"
        ),
    )

    assert client.get(items_url(stranger_household, theirs)).status_code == 404
    assert (
        client.post(
            items_url(stranger_household, theirs),
            {"item_type": tshirt.pk},
            content_type="application/json",
        ).status_code
        == 404
    )
    assert client.get(item_url(stranger_household, theirs, line)).status_code == 404
    assert (
        client.patch(
            item_url(stranger_household, theirs, line),
            {"quantity": 2},
            content_type="application/json",
        ).status_code
        == 404
    )
    assert client.delete(item_url(stranger_household, theirs, line)).status_code == 404


def test_a_line_of_another_trip_is_unreachable_through_our_own(
    client, household, trip, tshirt, to_pack
):
    other = Trip.objects.create(household=household, name="Noel", date="2025-12-24")
    line = TripItem.objects.create(trip=other, item_type=tshirt, status=to_pack)

    assert client.get(item_url(household, trip, line)).status_code == 404


def test_a_line_carries_the_kits_of_the_household_that_hold_its_object(
    client, household, trip, leo, tshirt, to_pack, rando
):
    langer = Kit.objects.create(household=household, name="Sac a langer")
    KitItem.objects.create(kit=rando, item_type=tshirt)
    KitItem.objects.create(kit=rando, item_type=tshirt, person=leo)
    KitItem.objects.create(kit=langer, item_type=tshirt)
    line = TripItem.objects.create(trip=trip, item_type=tshirt, status=to_pack)

    tagged = client.get(item_url(household, trip, line)).json()["kits"]

    assert tagged == [
        {"id": rando.pk, "name": "Affaires de rando", "description": "", "position": 0},
        {"id": langer.pk, "name": "Sac a langer", "description": "", "position": 1},
    ]


def test_the_tags_of_a_trip_cost_the_same_whatever_the_number_of_lines(
    client, household, trip, to_pack, rando, django_assert_num_queries
):
    def pack(indexes):
        for index in indexes:
            item_type = ItemType.objects.create(household=household, name=f"Objet {index}")
            KitItem.objects.create(kit=rando, item_type=item_type)
            TripItem.objects.create(trip=trip, item_type=item_type, status=to_pack)

    pack(range(2))
    with django_assert_num_queries(READING_A_TRIP_LIST_OF_LINES):
        client.get(items_url(household, trip))

    pack(range(2, 10))

    with django_assert_num_queries(READING_A_TRIP_LIST_OF_LINES):
        client.get(items_url(household, trip))


def test_choosing_a_kit_copies_its_lines_into_the_trip_in_its_own_order(
    client, household, trip, leo, tshirt, to_pack, rando
):
    TripParticipant.objects.create(trip=trip, person=leo)
    creme = ItemType.objects.create(household=household, name="Creme solaire")
    KitItem.objects.create(kit=rando, item_type=tshirt, person=leo, quantity=5)
    KitItem.objects.create(kit=rando, item_type=creme)

    response = client.post(
        kits_url(household, trip), {"kit": rando.pk}, content_type="application/json"
    )

    assert response.status_code == 201
    body = response.json()
    assert [entry["item_type"]["name"] for entry in body] == ["T-shirt", "Creme solaire"]
    assert body[0]["quantity"] == 5
    assert body[0]["person"]["name"] == "Leo"
    assert body[0]["status"]["id"] == to_pack.pk
    assert body[0]["kits"] == [
        {"id": rando.pk, "name": "Affaires de rando", "description": "", "position": 0}
    ]
    assert [line.position for line in trip.items.all()] == [0, 1]


def test_choosing_a_kit_ignores_the_lines_of_someone_who_does_not_go(
    client, household, trip, leo, tshirt, to_pack, rando
):
    stayed = Person.objects.create(household=household, name="Enfant 2")
    KitItem.objects.create(kit=rando, item_type=tshirt, person=stayed)
    KitItem.objects.create(kit=rando, item_type=tshirt, person=leo)
    TripParticipant.objects.create(trip=trip, person=leo)

    response = client.post(
        kits_url(household, trip), {"kit": rando.pk}, content_type="application/json"
    )

    assert response.status_code == 201
    assert [entry["person"]["name"] for entry in response.json()] == ["Leo"]
    assert trip.items.count() == 1


def test_choosing_a_kit_again_adds_only_what_is_missing_and_leaves_the_quantities_alone(
    client, household, trip, tshirt, to_pack, rando
):
    creme = ItemType.objects.create(household=household, name="Creme solaire")
    KitItem.objects.create(kit=rando, item_type=tshirt, quantity=5)
    client.post(kits_url(household, trip), {"kit": rando.pk}, content_type="application/json")
    trip.items.update(quantity=3)
    KitItem.objects.create(kit=rando, item_type=creme)

    response = client.post(
        kits_url(household, trip), {"kit": rando.pk}, content_type="application/json"
    )

    assert response.status_code == 201
    assert [entry["item_type"]["name"] for entry in response.json()] == ["Creme solaire"]
    assert trip.items.get(item_type=tshirt).quantity == 3


def test_a_kit_that_adds_nothing_answers_with_an_empty_array(
    client, household, trip, tshirt, to_pack, rando
):
    stayed = Person.objects.create(household=household, name="Enfant 2")
    KitItem.objects.create(kit=rando, item_type=tshirt, person=stayed)

    response = client.post(
        kits_url(household, trip), {"kit": rando.pk}, content_type="application/json"
    )

    assert response.status_code == 200
    assert response.json() == []
    assert not trip.items.exists()


def test_choosing_a_kit_twice_at_once_answers_that_the_race_left_nothing_to_add(
    client, household, trip, leo, tshirt, to_pack, rando, monkeypatch
):
    TripParticipant.objects.create(trip=trip, person=leo)
    KitItem.objects.create(kit=rando, item_type=tshirt, person=leo)
    client.post(kits_url(household, trip), {"kit": rando.pk}, content_type="application/json")
    monkeypatch.setattr(trips_preparation, "packed_lines", blind_to_the_first_reading(packed_lines))

    response = client.post(
        kits_url(household, trip), {"kit": rando.pk}, content_type="application/json"
    )

    assert response.status_code == 200
    assert response.json() == []
    assert trip.items.count() == 1


def test_a_kit_cannot_be_instantiated_by_a_household_that_has_no_status_yet(
    client, household, trip, tshirt, rando
):
    KitItem.objects.create(kit=rando, item_type=tshirt)

    response = client.post(
        kits_url(household, trip), {"kit": rando.pk}, content_type="application/json"
    )

    assert response.status_code == 409
    assert not trip.items.exists()


def test_a_kit_of_another_household_is_not_poured_into_our_trip(
    client, household, trip, to_pack, stranger_household
):
    theirs = Kit.objects.create(household=stranger_household, name="Le leur")
    KitItem.objects.create(
        kit=theirs,
        item_type=ItemType.objects.create(household=stranger_household, name="Le leur"),
    )

    response = client.post(
        kits_url(household, trip), {"kit": theirs.pk}, content_type="application/json"
    )

    assert response.status_code == 404
    assert not trip.items.exists()


def test_a_kit_is_not_poured_into_a_trip_of_another_household(
    client, stranger_household, rando, to_pack
):
    theirs = Trip.objects.create(household=stranger_household, name="Le leur", date="2026-07-14")

    response = client.post(
        kits_url(stranger_household, theirs), {"kit": rando.pk}, content_type="application/json"
    )

    assert response.status_code == 404
    assert not theirs.items.exists()


def test_duplicating_a_trip_repeats_its_people_and_its_lines_at_the_starting_status(
    client, household, trip, leo, tshirt, to_pack, packed
):
    TripParticipant.objects.create(trip=trip, person=leo)
    creme = ItemType.objects.create(household=household, name="Creme solaire")
    TripItem.objects.create(trip=trip, item_type=tshirt, person=leo, quantity=5, status=packed)
    TripItem.objects.create(trip=trip, item_type=creme, status=packed)

    response = client.post(
        duplicate_url(household, trip),
        {"name": "Bretagne 2027", "date": "2027-07-14"},
        content_type="application/json",
    )

    assert response.status_code == 201
    body = response.json()
    assert (body["name"], body["date"], body["archived_at"]) == (
        "Bretagne 2027",
        "2027-07-14",
        None,
    )
    assert [entry["person"]["name"] for entry in body["participants"]] == ["Leo"]
    assert [entry["item_type"]["name"] for entry in body["items"]] == ["T-shirt", "Creme solaire"]
    assert body["items"][0]["quantity"] == 5
    assert body["items"][0]["person"]["name"] == "Leo"
    assert [entry["position"] for entry in body["items"]] == [0, 1]
    assert {entry["status"]["id"] for entry in body["items"]} == {to_pack.pk}


def test_duplicating_a_trip_leaves_the_one_it_copies_alone(
    client, household, trip, leo, tshirt, to_pack, packed
):
    TripParticipant.objects.create(trip=trip, person=leo)
    line = TripItem.objects.create(trip=trip, item_type=tshirt, quantity=5, status=packed)

    client.post(
        duplicate_url(household, trip),
        {"name": "Bretagne 2027", "date": "2027-07-14"},
        content_type="application/json",
    )

    line.refresh_from_db()
    assert (line.status_id, line.quantity) == (packed.pk, 5)
    assert trip.items.count() == 1
    assert trip.participants.count() == 1


def test_the_copy_of_an_archived_trip_starts_in_the_current_list(
    client, household, trip, tshirt, to_pack
):
    TripItem.objects.create(trip=trip, item_type=tshirt, status=to_pack)
    trip.archived_at = timezone.now()
    trip.save()

    response = client.post(
        duplicate_url(household, trip),
        {"name": "Bretagne 2027", "date": "2027-07-14"},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert response.json()["archived_at"] is None
    assert [entry["name"] for entry in client.get(trips_url(household)).json()] == ["Bretagne 2027"]


def test_a_duplicate_without_a_name_or_without_a_date_is_refused(client, household, trip, to_pack):
    nameless = client.post(
        duplicate_url(household, trip), {"date": "2027-07-14"}, content_type="application/json"
    )
    dateless = client.post(
        duplicate_url(household, trip), {"name": "Bretagne 2027"}, content_type="application/json"
    )

    assert [nameless.status_code, dateless.status_code] == [400, 400]
    assert household.trips.count() == 1


def test_a_trip_cannot_be_duplicated_by_a_household_that_has_no_status_yet(
    client, household, trip, tshirt
):
    response = client.post(
        duplicate_url(household, trip),
        {"name": "Bretagne 2027", "date": "2027-07-14"},
        content_type="application/json",
    )

    assert response.status_code == 409
    assert household.trips.count() == 1


def test_a_trip_of_another_household_is_not_duplicated(client, stranger_household, to_pack):
    theirs = Trip.objects.create(household=stranger_household, name="Le leur", date="2026-07-14")

    response = client.post(
        duplicate_url(stranger_household, theirs),
        {"name": "Le mien", "date": "2027-07-14"},
        content_type="application/json",
    )

    assert response.status_code == 404
    assert stranger_household.trips.count() == 1
