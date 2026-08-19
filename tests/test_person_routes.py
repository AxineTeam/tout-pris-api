from app.models import Person


def test_create_person_returns_the_created_person(authenticated_client, household):
    response = authenticated_client.post(
        f"/households/{household.id}/persons", json={"name": "Alice"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Alice"
    assert body["household_id"] == household.id
    assert body["user_id"] is None


def test_create_person_rejects_a_blank_name(authenticated_client, household):
    response = authenticated_client.post(f"/households/{household.id}/persons", json={"name": " "})

    assert response.status_code == 422


def test_create_person_ignores_a_client_supplied_household(authenticated_client, household):
    response = authenticated_client.post(
        f"/households/{household.id}/persons",
        json={"name": "Alice", "household_id": 404404, "user_id": 404404},
    )

    assert response.status_code == 201
    assert response.json()["household_id"] == household.id
    assert response.json()["user_id"] is None


def test_create_person_hides_a_household_of_another_user(authenticated_client, db, other_household):
    response = authenticated_client.post(
        f"/households/{other_household.id}/persons", json={"name": "Intruse"}
    )

    assert response.status_code == 404
    assert db.query(Person).filter(Person.name == "Intruse").count() == 0


def test_create_person_answers_404_on_an_unknown_household(authenticated_client):
    response = authenticated_client.post("/households/404404/persons", json={"name": "Alice"})

    assert response.status_code == 404


def test_create_person_requires_authentication(client, household):
    response = client.post(f"/households/{household.id}/persons", json={"name": "Alice"})

    assert response.status_code == 401


def test_list_persons_returns_only_the_persons_of_the_household(
    authenticated_client, household, person, other_person
):
    response = authenticated_client.get(f"/households/{household.id}/persons")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [person.id]


def test_list_persons_hides_a_household_of_another_user(authenticated_client, other_household):
    response = authenticated_client.get(f"/households/{other_household.id}/persons")

    assert response.status_code == 404


def test_list_persons_answers_404_on_an_unknown_household(authenticated_client):
    response = authenticated_client.get("/households/404404/persons")

    assert response.status_code == 404


def test_list_persons_requires_authentication(client, household):
    response = client.get(f"/households/{household.id}/persons")

    assert response.status_code == 401


def test_read_person_returns_a_person_of_the_household(authenticated_client, household, person):
    response = authenticated_client.get(f"/households/{household.id}/persons/{person.id}")

    assert response.status_code == 200
    assert response.json()["name"] == "Alice"


def test_read_person_hides_a_person_of_another_household(
    authenticated_client, household, other_person
):
    response = authenticated_client.get(f"/households/{household.id}/persons/{other_person.id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Person not found"


def test_read_person_hides_a_person_through_the_household_of_its_owner(
    authenticated_client, other_household, other_person
):
    response = authenticated_client.get(
        f"/households/{other_household.id}/persons/{other_person.id}"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Household not found"


def test_read_person_answers_404_on_an_unknown_person(authenticated_client, household):
    response = authenticated_client.get(f"/households/{household.id}/persons/404404")

    assert response.status_code == 404


def test_read_person_requires_authentication(client, household, person):
    response = client.get(f"/households/{household.id}/persons/{person.id}")

    assert response.status_code == 401


def test_update_person_renames_it(authenticated_client, stored, household, person):
    response = authenticated_client.patch(
        f"/households/{household.id}/persons/{person.id}", json={"name": "Alicia"}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Alicia"
    assert stored(Person, person.id).name == "Alicia"


def test_update_person_leaves_omitted_fields_untouched(authenticated_client, household, person):
    response = authenticated_client.patch(
        f"/households/{household.id}/persons/{person.id}", json={}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Alice"


def test_update_person_treats_an_explicit_null_as_no_change(
    authenticated_client, household, person
):
    response = authenticated_client.patch(
        f"/households/{household.id}/persons/{person.id}", json={"name": None}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Alice"


def test_update_person_rejects_a_blank_name(authenticated_client, household, person):
    response = authenticated_client.patch(
        f"/households/{household.id}/persons/{person.id}", json={"name": ""}
    )

    assert response.status_code == 422


def test_update_person_hides_a_person_of_another_household(
    authenticated_client, stored, household, other_person
):
    response = authenticated_client.patch(
        f"/households/{household.id}/persons/{other_person.id}", json={"name": "Détournée"}
    )

    assert response.status_code == 404
    assert stored(Person, other_person.id).name == "Bob"


def test_update_person_answers_404_on_an_unknown_person(authenticated_client, household):
    response = authenticated_client.patch(
        f"/households/{household.id}/persons/404404", json={"name": "Alicia"}
    )

    assert response.status_code == 404


def test_update_person_requires_authentication(client, household, person):
    response = client.patch(
        f"/households/{household.id}/persons/{person.id}", json={"name": "Alicia"}
    )

    assert response.status_code == 401


def test_delete_person_removes_it(authenticated_client, stored, household, person):
    response = authenticated_client.delete(f"/households/{household.id}/persons/{person.id}")

    assert response.status_code == 204
    assert stored(Person, person.id) is None


def test_delete_person_hides_a_person_of_another_household(
    authenticated_client, stored, household, other_person
):
    response = authenticated_client.delete(f"/households/{household.id}/persons/{other_person.id}")

    assert response.status_code == 404
    assert stored(Person, other_person.id) is not None


def test_delete_person_answers_404_on_an_unknown_person(authenticated_client, household):
    response = authenticated_client.delete(f"/households/{household.id}/persons/404404")

    assert response.status_code == 404


def test_delete_person_requires_authentication(client, household, person):
    response = client.delete(f"/households/{household.id}/persons/{person.id}")

    assert response.status_code == 401
