import pytest
from django.test import Client

from accounts.models import User
from catalog.models import ItemType, Kit, KitItem
from households.models import Household, HouseholdMember, Person

pytestmark = pytest.mark.django_db


def kits_url(household):
    return f"/api/households/{household.pk}/kits/"


def kit_url(household, kit):
    return f"{kits_url(household)}{kit.pk}/"


def kit_items_url(household, kit):
    return f"{kit_url(household, kit)}items/"


def kit_item_url(household, kit, line):
    return f"{kit_items_url(household, kit)}{line.pk}/"


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
def kit(household):
    return Kit.objects.create(household=household, name="Sac a langer")


@pytest.fixture
def bavoir(household):
    return ItemType.objects.create(household=household, name="Bavoir")


def test_the_kits_of_a_household_are_listed_in_display_order(client, household):
    Kit.objects.create(household=household, name="Sac a langer")
    Kit.objects.create(household=household, name="Affaires de rando")

    listed = client.get(kits_url(household)).json()

    assert [entry["name"] for entry in listed] == ["Sac a langer", "Affaires de rando"]
    assert [entry["position"] for entry in listed] == [0, 1]


def test_the_kit_list_does_not_carry_the_lines_the_kit_read_alone_does(
    client, household, kit, bavoir
):
    KitItem.objects.create(kit=kit, item_type=bavoir)

    listed = client.get(kits_url(household)).json()

    assert listed == [{"id": kit.pk, "name": "Sac a langer", "description": "", "position": 0}]
    assert len(client.get(kit_url(household, kit)).json()["items"]) == 1


def test_creating_a_kit_appends_it_to_the_household_list(client, household):
    Kit.objects.create(household=household, name="Sac a langer")

    response = client.post(
        kits_url(household),
        {"name": "Affaires de rando", "description": "Pour la montagne"},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert response.json()["position"] == 1
    assert household.kits.filter(name="Affaires de rando", description="Pour la montagne").exists()


def test_a_kit_is_read_with_its_lines_in_preparation_order(client, household, kit, bavoir):
    louis = Person.objects.create(household=household, name="Louis")
    KitItem.objects.create(kit=kit, item_type=bavoir, person=louis, quantity=2)
    KitItem.objects.create(kit=kit, item_type=bavoir)

    response = client.get(kit_url(household, kit))

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Sac a langer"
    assert body["items"][0] == {
        "id": body["items"][0]["id"],
        "item_type": {"id": bavoir.pk, "name": "Bavoir", "description": ""},
        "person": {"id": louis.pk, "name": "Louis", "user": None},
        "quantity": 2,
        "position": 0,
    }
    assert body["items"][1]["person"] is None
    assert [line["position"] for line in body["items"]] == [0, 1]


def test_a_kit_is_renamed_and_described(client, household, kit):
    response = client.patch(
        kit_url(household, kit),
        {"name": "Sac a langer du soir", "description": "Le minimum"},
        content_type="application/json",
    )

    assert response.status_code == 200
    kit.refresh_from_db()
    assert (kit.name, kit.description) == ("Sac a langer du soir", "Le minimum")


def test_deleting_a_kit_takes_its_lines_with_it(client, household, kit, bavoir):
    line = KitItem.objects.create(kit=kit, item_type=bavoir)

    response = client.delete(kit_url(household, kit))

    assert response.status_code == 204
    assert not Kit.objects.filter(pk=kit.pk).exists()
    assert not KitItem.objects.filter(pk=line.pk).exists()


def test_the_kits_of_another_household_are_out_of_reach(client, stranger_household):
    theirs = Kit.objects.create(household=stranger_household, name="Le leur")

    assert client.get(kits_url(stranger_household)).status_code == 404
    assert (
        client.post(
            kits_url(stranger_household), {"name": "Le mien"}, content_type="application/json"
        ).status_code
        == 404
    )
    assert client.get(kit_url(stranger_household, theirs)).status_code == 404
    assert (
        client.patch(
            kit_url(stranger_household, theirs),
            {"name": "Le mien"},
            content_type="application/json",
        ).status_code
        == 404
    )
    assert client.delete(kit_url(stranger_household, theirs)).status_code == 404


def test_a_kit_of_another_household_is_unreachable_through_our_own(
    client, household, stranger_household
):
    theirs = Kit.objects.create(household=stranger_household, name="Le leur")

    assert client.get(kit_url(household, theirs)).status_code == 404


def test_the_kit_endpoints_refuse_an_unauthenticated_caller(household, kit):
    anonymous = Client()

    assert anonymous.get(kits_url(household)).status_code == 401
    assert anonymous.post(kits_url(household), {"name": "Le mien"}).status_code == 401
    assert anonymous.get(kit_items_url(household, kit)).status_code == 401


def test_a_member_who_is_nobody_yet_reads_the_kits_but_does_not_write_them(household, kit, bavoir):
    newcomer = User.objects.create_user(username="lou", email="lou@example.com")
    HouseholdMember.objects.create(household=household, user=newcomer)
    client = signed_in(newcomer)

    assert client.get(kits_url(household)).status_code == 200
    assert client.get(kit_items_url(household, kit)).status_code == 200
    assert (
        client.post(
            kits_url(household), {"name": "Le mien"}, content_type="application/json"
        ).status_code
        == 403
    )
    assert (
        client.post(
            kit_items_url(household, kit),
            {"item_type": bavoir.pk},
            content_type="application/json",
        ).status_code
        == 403
    )


def test_the_lines_of_a_kit_are_listed_in_preparation_order(client, household, kit, bavoir):
    KitItem.objects.create(kit=kit, item_type=bavoir, quantity=2)
    KitItem.objects.create(kit=kit, item_type=bavoir, quantity=5)

    listed = client.get(kit_items_url(household, kit)).json()

    assert [line["quantity"] for line in listed] == [2, 5]
    assert [line["position"] for line in listed] == [0, 1]


def test_adding_a_line_to_a_kit_appends_it(client, household, kit, bavoir):
    louis = Person.objects.create(household=household, name="Louis")
    KitItem.objects.create(kit=kit, item_type=bavoir)

    response = client.post(
        kit_items_url(household, kit),
        {"item_type": bavoir.pk, "person": louis.pk, "quantity": 5},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert response.json()["item_type"] == {"id": bavoir.pk, "name": "Bavoir", "description": ""}
    assert response.json()["person"]["name"] == "Louis"
    assert response.json()["position"] == 1
    assert kit.items.filter(quantity=5, person=louis).exists()


def test_a_line_without_a_person_is_for_the_whole_household(client, household, kit, bavoir):
    response = client.post(
        kit_items_url(household, kit),
        {"item_type": bavoir.pk},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert response.json()["person"] is None
    assert response.json()["quantity"] == 1


def test_the_same_item_type_is_packed_twice_in_the_same_kit(client, household, kit, bavoir):
    jeanne = Person.objects.create(household=household, name="Jeanne")

    first = client.post(
        kit_items_url(household, kit),
        {"item_type": bavoir.pk},
        content_type="application/json",
    )
    second = client.post(
        kit_items_url(household, kit),
        {"item_type": bavoir.pk, "person": jeanne.pk},
        content_type="application/json",
    )

    assert (first.status_code, second.status_code) == (201, 201)
    assert kit.items.count() == 2


def test_a_line_is_read_one_by_one(client, household, kit, bavoir):
    line = KitItem.objects.create(kit=kit, item_type=bavoir, quantity=3)

    response = client.get(kit_item_url(household, kit, line))

    assert response.status_code == 200
    assert response.json() == {
        "id": line.pk,
        "item_type": {"id": bavoir.pk, "name": "Bavoir", "description": ""},
        "person": None,
        "quantity": 3,
        "position": 0,
    }


def test_a_line_changes_its_quantity_its_object_and_its_person(client, household, kit, bavoir):
    chapeau = ItemType.objects.create(household=household, name="Chapeau")
    louis = Person.objects.create(household=household, name="Louis")
    line = KitItem.objects.create(kit=kit, item_type=bavoir)

    response = client.patch(
        kit_item_url(household, kit, line),
        {"item_type": chapeau.pk, "person": louis.pk, "quantity": 4},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["item_type"]["name"] == "Chapeau"
    line.refresh_from_db()
    assert (line.item_type_id, line.person_id, line.quantity) == (chapeau.pk, louis.pk, 4)


def test_a_line_aimed_at_someone_becomes_common_again(client, household, kit, bavoir):
    louis = Person.objects.create(household=household, name="Louis")
    line = KitItem.objects.create(kit=kit, item_type=bavoir, person=louis)

    response = client.patch(
        kit_item_url(household, kit, line),
        {"person": None},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["person"] is None
    line.refresh_from_db()
    assert line.person_id is None


def test_a_line_that_drops_its_item_type_is_refused(client, household, kit, bavoir):
    line = KitItem.objects.create(kit=kit, item_type=bavoir)

    response = client.patch(
        kit_item_url(household, kit, line),
        {"item_type": None},
        content_type="application/json",
    )

    assert response.status_code == 400
    line.refresh_from_db()
    assert line.item_type_id == bavoir.pk


def test_a_line_packs_at_least_one_of_something(client, household, kit, bavoir):
    line = KitItem.objects.create(kit=kit, item_type=bavoir, quantity=3)

    response = client.patch(
        kit_item_url(household, kit, line), {"quantity": 0}, content_type="application/json"
    )

    assert response.status_code == 400
    line.refresh_from_db()
    assert line.quantity == 3


def test_a_line_packs_no_more_than_a_small_integer_holds(client, household, kit, bavoir):
    response = client.post(
        kit_items_url(household, kit),
        {"item_type": bavoir.pk, "quantity": 40000},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not kit.items.exists()


def test_a_line_is_deleted(client, household, kit, bavoir):
    line = KitItem.objects.create(kit=kit, item_type=bavoir)

    response = client.delete(kit_item_url(household, kit, line))

    assert response.status_code == 204
    assert not KitItem.objects.filter(pk=line.pk).exists()


def test_a_line_cannot_pack_an_item_type_of_another_household(
    client, household, kit, bavoir, stranger_household
):
    theirs = ItemType.objects.create(household=stranger_household, name="Le leur")
    line = KitItem.objects.create(kit=kit, item_type=bavoir)

    created = client.post(
        kit_items_url(household, kit),
        {"item_type": theirs.pk},
        content_type="application/json",
    )
    patched = client.patch(
        kit_item_url(household, kit, line),
        {"item_type": theirs.pk},
        content_type="application/json",
    )

    assert (created.status_code, patched.status_code) == (404, 404)
    assert kit.items.count() == 1
    line.refresh_from_db()
    assert line.item_type_id == bavoir.pk


def test_a_line_cannot_aim_at_a_person_of_another_household(
    client, household, kit, bavoir, stranger_household
):
    theirs = Person.objects.create(household=stranger_household, name="Sacha")
    line = KitItem.objects.create(kit=kit, item_type=bavoir)

    created = client.post(
        kit_items_url(household, kit),
        {"item_type": bavoir.pk, "person": theirs.pk},
        content_type="application/json",
    )
    patched = client.patch(
        kit_item_url(household, kit, line),
        {"person": theirs.pk},
        content_type="application/json",
    )

    assert (created.status_code, patched.status_code) == (404, 404)
    assert kit.items.count() == 1
    line.refresh_from_db()
    assert line.person_id is None


def test_a_line_that_names_no_item_type_at_all_is_refused(client, household, kit):
    response = client.post(kit_items_url(household, kit), {}, content_type="application/json")

    assert response.status_code == 400
    assert not kit.items.exists()


def test_an_item_type_that_is_not_an_identifier_is_a_broken_body(client, household, kit):
    response = client.post(
        kit_items_url(household, kit), {"item_type": "Bavoir"}, content_type="application/json"
    )

    assert response.status_code == 400
    assert not kit.items.exists()


def test_the_lines_of_a_kit_of_another_household_are_out_of_reach(
    client, stranger_household, bavoir
):
    theirs = Kit.objects.create(household=stranger_household, name="Le leur")
    line = KitItem.objects.create(
        kit=theirs,
        item_type=ItemType.objects.create(household=stranger_household, name="Le leur"),
    )

    assert client.get(kit_items_url(stranger_household, theirs)).status_code == 404
    assert (
        client.post(
            kit_items_url(stranger_household, theirs),
            {"item_type": bavoir.pk},
            content_type="application/json",
        ).status_code
        == 404
    )
    assert client.get(kit_item_url(stranger_household, theirs, line)).status_code == 404
    assert (
        client.patch(
            kit_item_url(stranger_household, theirs, line),
            {"quantity": 2},
            content_type="application/json",
        ).status_code
        == 404
    )
    assert client.delete(kit_item_url(stranger_household, theirs, line)).status_code == 404


def test_a_kit_of_another_household_is_not_filled_through_our_own_household(
    client, household, stranger_household, bavoir
):
    theirs = Kit.objects.create(household=stranger_household, name="Le leur")

    response = client.post(
        kit_items_url(household, theirs),
        {"item_type": bavoir.pk},
        content_type="application/json",
    )

    assert response.status_code == 404
    assert not theirs.items.exists()


def test_a_line_of_another_kit_is_unreachable_through_our_own(client, household, kit, bavoir):
    other = Kit.objects.create(household=household, name="Affaires de rando")
    line = KitItem.objects.create(kit=other, item_type=bavoir)

    assert client.get(kit_item_url(household, kit, line)).status_code == 404


def test_a_kit_moves_to_the_rank_it_is_given(client, household):
    Kit.objects.create(household=household, name="Sac a langer")
    Kit.objects.create(household=household, name="Affaires de rando")
    last = Kit.objects.create(household=household, name="Plage")

    response = client.patch(
        kit_url(household, last), {"position": 0}, content_type="application/json"
    )

    assert response.status_code == 200
    assert response.json()["position"] == 0
    listed = client.get(kits_url(household)).json()
    assert [entry["name"] for entry in listed] == ["Plage", "Sac a langer", "Affaires de rando"]
    assert [entry["position"] for entry in listed] == [0, 1, 2]


def test_a_kit_does_not_move_past_the_end_of_the_household_list(client, household, kit):
    last = Kit.objects.create(household=household, name="Plage")

    response = client.patch(
        kit_url(household, last), {"position": 2}, content_type="application/json"
    )

    assert response.status_code == 400
    last.refresh_from_db()
    assert last.position == 1


def test_a_line_moves_to_the_rank_it_is_given(client, household, kit, bavoir):
    gourde = ItemType.objects.create(household=household, name="Gourde")
    chaussures = ItemType.objects.create(household=household, name="Chaussures")
    KitItem.objects.create(kit=kit, item_type=bavoir)
    KitItem.objects.create(kit=kit, item_type=gourde)
    shoes = KitItem.objects.create(kit=kit, item_type=chaussures)

    response = client.patch(
        kit_item_url(household, kit, shoes), {"position": 0}, content_type="application/json"
    )

    assert response.status_code == 200
    assert response.json()["position"] == 0
    lines = client.get(kit_url(household, kit)).json()["items"]
    assert [line["item_type"]["name"] for line in lines] == ["Chaussures", "Bavoir", "Gourde"]
    assert [line["position"] for line in lines] == [0, 1, 2]


def test_a_line_does_not_move_past_the_end_of_its_kit(client, household, kit, bavoir):
    KitItem.objects.create(kit=kit, item_type=bavoir)
    last = KitItem.objects.create(kit=kit, item_type=bavoir)

    response = client.patch(
        kit_item_url(household, kit, last), {"position": 2}, content_type="application/json"
    )

    assert response.status_code == 400
    last.refresh_from_db()
    assert last.position == 1


def test_a_line_does_not_move_before_the_head_of_its_kit(client, household, kit, bavoir):
    KitItem.objects.create(kit=kit, item_type=bavoir)
    last = KitItem.objects.create(kit=kit, item_type=bavoir)

    response = client.patch(
        kit_item_url(household, kit, last), {"position": -1}, content_type="application/json"
    )

    assert response.status_code == 400
    last.refresh_from_db()
    assert last.position == 1


def test_a_line_moves_within_its_own_kit(client, household, kit, bavoir):
    elsewhere = Kit.objects.create(household=household, name="Affaires de rando")
    KitItem.objects.create(kit=elsewhere, item_type=bavoir)
    KitItem.objects.create(kit=elsewhere, item_type=bavoir)
    KitItem.objects.create(kit=elsewhere, item_type=bavoir)
    mine = KitItem.objects.create(kit=kit, item_type=bavoir)

    response = client.patch(
        kit_item_url(household, kit, mine), {"position": 2}, content_type="application/json"
    )

    assert response.status_code == 400
    mine.refresh_from_db()
    assert mine.position == 0
