from sqlalchemy import select

from app.models import Household, HouseholdMember, HouseholdRole


def test_create_household_returns_the_created_household(authenticated_client):
    response = authenticated_client.post("/households", json={"name": "Maison"})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Maison"
    assert body["id"] > 0
    assert body["created_at"]


def test_create_household_makes_the_creator_an_owner(authenticated_client, db, user):
    household_id = authenticated_client.post("/households", json={"name": "Maison"}).json()["id"]

    membership = db.scalar(
        select(HouseholdMember).where(
            HouseholdMember.household_id == household_id,
            HouseholdMember.user_id == user.id,
        )
    )
    assert membership is not None
    assert membership.role == HouseholdRole.owner


def test_create_household_rejects_a_blank_name(authenticated_client):
    response = authenticated_client.post("/households", json={"name": "   "})

    assert response.status_code == 422


def test_create_household_requires_authentication(client):
    response = client.post("/households", json={"name": "Maison"})

    assert response.status_code == 401


def test_list_households_returns_only_the_households_of_the_caller(
    authenticated_client, household, other_household
):
    response = authenticated_client.get("/households")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [household.id]


def test_list_households_returns_an_empty_array_without_membership(authenticated_client):
    response = authenticated_client.get("/households")

    assert response.status_code == 200
    assert response.json() == []


def test_list_households_requires_authentication(client):
    response = client.get("/households")

    assert response.status_code == 401


def test_read_household_returns_a_household_of_the_caller(authenticated_client, household):
    response = authenticated_client.get(f"/households/{household.id}")

    assert response.status_code == 200
    assert response.json()["name"] == "Maison"


def test_read_household_hides_a_household_of_another_user(authenticated_client, other_household):
    response = authenticated_client.get(f"/households/{other_household.id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Household not found"


def test_read_household_answers_404_on_an_unknown_household(authenticated_client):
    response = authenticated_client.get("/households/404404")

    assert response.status_code == 404


def test_read_household_requires_authentication(client, household):
    response = client.get(f"/households/{household.id}")

    assert response.status_code == 401


def test_update_household_renames_it(authenticated_client, stored, household):
    response = authenticated_client.patch(
        f"/households/{household.id}", json={"name": "Maison de campagne"}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Maison de campagne"
    assert stored(Household, household.id).name == "Maison de campagne"


def test_update_household_leaves_omitted_fields_untouched(authenticated_client, household):
    response = authenticated_client.patch(f"/households/{household.id}", json={})

    assert response.status_code == 200
    assert response.json()["name"] == "Maison"


def test_update_household_treats_an_explicit_null_as_no_change(authenticated_client, household):
    response = authenticated_client.patch(f"/households/{household.id}", json={"name": None})

    assert response.status_code == 200
    assert response.json()["name"] == "Maison"


def test_update_household_rejects_a_blank_name(authenticated_client, household):
    response = authenticated_client.patch(f"/households/{household.id}", json={"name": ""})

    assert response.status_code == 422


def test_update_household_hides_a_household_of_another_user(
    authenticated_client, stored, other_household
):
    response = authenticated_client.patch(
        f"/households/{other_household.id}", json={"name": "Détournée"}
    )

    assert response.status_code == 404
    assert stored(Household, other_household.id).name == "Chez les autres"


def test_update_household_answers_404_on_an_unknown_household(authenticated_client):
    response = authenticated_client.patch("/households/404404", json={"name": "Maison"})

    assert response.status_code == 404


def test_update_household_requires_authentication(client, household):
    response = client.patch(f"/households/{household.id}", json={"name": "Maison"})

    assert response.status_code == 401


def test_delete_household_removes_it_with_its_members_and_persons(
    authenticated_client, db, stored, household, person
):
    response = authenticated_client.delete(f"/households/{household.id}")

    assert response.status_code == 204
    assert stored(Household, household.id) is None
    assert db.scalars(select(HouseholdMember)).all() == []


def test_delete_household_hides_a_household_of_another_user(
    authenticated_client, stored, other_household
):
    response = authenticated_client.delete(f"/households/{other_household.id}")

    assert response.status_code == 404
    assert stored(Household, other_household.id) is not None


def test_delete_household_answers_404_on_an_unknown_household(authenticated_client):
    response = authenticated_client.delete("/households/404404")

    assert response.status_code == 404


def test_delete_household_requires_authentication(client, household):
    response = client.delete(f"/households/{household.id}")

    assert response.status_code == 401
