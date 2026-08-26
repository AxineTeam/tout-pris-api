import datetime

import pytest
from django.db import IntegrityError
from django.db.models import RestrictedError

from catalog.models import ItemStatus, ItemType
from households.models import Household, Person
from trips.models import Trip, TripItem, TripParticipant

pytestmark = pytest.mark.django_db


@pytest.fixture
def household():
    return Household.objects.create(name="Chez nous")


@pytest.fixture
def status(household):
    return ItemStatus.objects.create(household=household, name="Pas prepare", color="#94a3b8")


@pytest.fixture
def item_type(household):
    return ItemType.objects.create(household=household, name="Bavoir")


@pytest.fixture
def other_item_type(household):
    return ItemType.objects.create(household=household, name="Chapeau")


@pytest.fixture
def trip(household):
    return Trip.objects.create(
        household=household,
        name="Une semaine en Bretagne",
        date=datetime.date(2026, 7, 4),
    )


def make_line(trip, item_type, status, **fields):
    return TripItem.objects.create(trip=trip, item_type=item_type, status=status, **fields)


def test_a_trip_is_named_after_its_name(trip):
    assert str(trip) == "Une semaine en Bretagne"


def test_a_trip_line_reads_as_a_quantity_of_an_item_type(trip, item_type, status):
    assert str(make_line(trip, item_type, status, quantity=2)) == "2 Bavoir"


def test_a_person_takes_part_in_a_trip_only_once(trip, household):
    person = Person.objects.create(household=household, name="Enfant 1")
    TripParticipant.objects.create(trip=trip, person=person)

    with pytest.raises(IntegrityError):
        TripParticipant.objects.create(trip=trip, person=person)


def test_a_person_takes_part_in_several_trips(trip, household):
    person = Person.objects.create(household=household, name="Enfant 1")
    other_trip = Trip.objects.create(
        household=household,
        name="Noel chez les grands-parents",
        date=datetime.date(2026, 12, 24),
    )
    TripParticipant.objects.create(trip=trip, person=person)
    TripParticipant.objects.create(trip=other_trip, person=person)

    assert person.trip_participations.count() == 2


def test_a_common_item_type_enters_a_trip_only_once(trip, item_type, status):
    make_line(trip, item_type, status, quantity=2)

    with pytest.raises(IntegrityError):
        make_line(trip, item_type, status, quantity=6)


def test_an_item_type_enters_a_trip_only_once_for_the_same_person(
    trip, item_type, status, household
):
    person = Person.objects.create(household=household, name="Enfant 1")
    make_line(trip, item_type, status, person=person, quantity=2)

    with pytest.raises(IntegrityError):
        make_line(trip, item_type, status, person=person, quantity=6)


def test_the_same_item_type_enters_a_trip_once_per_person_and_once_for_everyone(
    trip, item_type, status, household
):
    first_child = Person.objects.create(household=household, name="Enfant 1")
    second_child = Person.objects.create(household=household, name="Enfant 2")

    make_line(trip, item_type, status, person=first_child)
    make_line(trip, item_type, status, person=second_child)
    make_line(trip, item_type, status)

    assert trip.items.count() == 3


def test_trip_lines_are_numbered_within_their_trip(
    trip, item_type, other_item_type, status, household
):
    other_trip = Trip.objects.create(
        household=household,
        name="Week-end a Paris",
        date=datetime.date(2026, 9, 5),
    )

    first = make_line(trip, item_type, status)
    second = make_line(trip, other_item_type, status)
    elsewhere = make_line(other_trip, item_type, status)

    assert [first.position, second.position, elsewhere.position] == [0, 1, 0]


def test_deleting_a_trip_line_closes_the_gap_it_leaves(
    trip, item_type, other_item_type, status, household
):
    third_item_type = ItemType.objects.create(household=household, name="Maillot de bain")

    make_line(trip, item_type, status)
    dropped = make_line(trip, other_item_type, status)
    last = make_line(trip, third_item_type, status)

    dropped.delete()
    last.refresh_from_db()

    assert last.position == 1


def test_deleting_a_trip_takes_away_its_lines_and_its_participants(
    trip, item_type, status, household
):
    TripParticipant.objects.create(
        trip=trip, person=Person.objects.create(household=household, name="Enfant 1")
    )
    make_line(trip, item_type, status)

    trip.delete()

    assert not TripItem.objects.exists()
    assert not TripParticipant.objects.exists()


def test_deleting_an_item_type_takes_away_the_trip_lines_packing_it(trip, item_type, status):
    make_line(trip, item_type, status)

    item_type.delete()

    assert not TripItem.objects.exists()


def test_deleting_a_person_keeps_the_trip_lines_aimed_at_them_and_makes_them_common(
    trip, item_type, status, household
):
    person = Person.objects.create(household=household, name="Enfant 1")
    line = make_line(trip, item_type, status, person=person)

    person.delete()
    line.refresh_from_db()

    assert line.person_id is None


def test_deleting_a_person_who_only_takes_part_in_a_trip_drops_their_participation(trip, household):
    person = Person.objects.create(household=household, name="Enfant 1")
    TripParticipant.objects.create(trip=trip, person=person)

    person.delete()

    assert not TripParticipant.objects.exists()


def test_deleting_a_status_a_trip_line_carries_is_refused(trip, item_type, status):
    make_line(trip, item_type, status)

    with pytest.raises(RestrictedError):
        status.delete()

    assert ItemStatus.objects.filter(pk=status.pk).exists()


def test_deleting_a_household_takes_away_its_trips_and_everything_they_hold(
    trip, item_type, status, household
):
    person = Person.objects.create(household=household, name="Enfant 1")
    TripParticipant.objects.create(trip=trip, person=person)
    make_line(trip, item_type, status, person=person)

    household.delete()

    assert not Trip.objects.exists()
    assert not TripItem.objects.exists()
    assert not TripParticipant.objects.exists()
    assert not Person.objects.exists()


def test_trips_are_listed_from_the_most_recent_departure(household, trip):
    older = Trip.objects.create(
        household=household,
        name="Paques a la campagne",
        date=datetime.date(2026, 4, 4),
    )

    assert list(household.trips.all()) == [trip, older]


def test_two_trips_leaving_the_same_day_are_listed_from_the_last_created(household, trip):
    same_day = Trip.objects.create(household=household, name="Piscine", date=trip.date)

    assert list(household.trips.all()) == [same_day, trip]
