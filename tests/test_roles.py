import pytest
from django.test import Client

from accounts.models import User
from households.invitations import invite
from households.memberships import create_household
from households.models import Household, HouseholdMember, HouseholdRole, Invitation, Person

pytestmark = pytest.mark.django_db


def signed_in(user):
    client = Client()
    client.force_login(user)
    return client


def household_url(household):
    return f"/api/households/{household.pk}/"


def persons_url(household):
    return f"{household_url(household)}persons/"


def members_url(household):
    return f"{household_url(household)}members/"


def invitations_url(household):
    return f"{household_url(household)}invitations/"


def membership_url(household, user):
    membership = HouseholdMember.objects.get(household=household, user=user)
    return f"{members_url(household)}{membership.pk}/"


@pytest.fixture
def owner():
    return User.objects.create_user(
        username="camille", email="camille@example.com", first_name="Camille"
    )


@pytest.fixture
def household(owner):
    return create_household("Famille Martin", owner)


@pytest.fixture
def member(household):
    user = User.objects.create_user(username="sacha", email="sacha@example.com", first_name="Sacha")
    HouseholdMember.objects.create(household=household, user=user)
    Person.objects.create(household=household, user=user, name="Sacha")
    return user


@pytest.fixture
def newcomer(household):
    user = User.objects.create_user(username="alex", email="alex@example.com", first_name="Alex")
    HouseholdMember.objects.create(household=household, user=user)
    return user


def test_a_member_neither_renames_nor_deletes_the_household(household, member):
    client = signed_in(member)

    renamed = client.patch(
        household_url(household), {"name": "Chez Sacha"}, content_type="application/json"
    )

    assert renamed.status_code == 403
    assert client.delete(household_url(household)).status_code == 403
    assert Household.objects.filter(pk=household.pk, name="Famille Martin").exists()


def test_an_owner_renames_and_deletes_the_household(household, owner):
    client = signed_in(owner)

    renamed = client.patch(
        household_url(household), {"name": "Les Martin"}, content_type="application/json"
    )

    assert renamed.status_code == 200
    assert client.delete(household_url(household)).status_code == 204


def test_a_member_neither_invites_nor_cancels_an_invitation(household, member, owner):
    pending = invite(household, "guest@example.com", owner)
    client = signed_in(member)

    invited = client.post(
        invitations_url(household), {"email": "other@example.com"}, content_type="application/json"
    )

    assert invited.status_code == 403
    assert client.delete(f"{invitations_url(household)}{pending.pk}/").status_code == 403
    assert Invitation.objects.filter(pk=pending.pk).exists()


def test_a_member_reads_the_household_like_an_owner(household, member):
    client = signed_in(member)

    assert client.get(persons_url(household)).status_code == 200
    assert client.get(members_url(household)).status_code == 200
    assert client.get(invitations_url(household)).status_code == 200


def test_a_member_creates_renames_and_deletes_the_persons(household, member):
    client = signed_in(member)

    created = client.post(
        persons_url(household), {"name": "Jeanne"}, content_type="application/json"
    )

    assert created.status_code == 201
    jeanne = f"{persons_url(household)}{created.json()['id']}/"
    assert (
        client.patch(jeanne, {"name": "Louis"}, content_type="application/json").status_code == 200
    )
    assert client.delete(jeanne).status_code == 204


def test_a_member_does_not_remove_another_member(household, member, owner):
    response = signed_in(member).delete(membership_url(household, owner))

    assert response.status_code == 403
    assert HouseholdMember.objects.filter(household=household, user=owner).exists()


def test_a_member_leaves_on_their_own(household, member):
    response = signed_in(member).delete(membership_url(household, member))

    assert response.status_code == 204
    assert not HouseholdMember.objects.filter(household=household, user=member).exists()


def test_a_member_does_not_hand_out_roles(household, member):
    response = signed_in(member).patch(
        membership_url(household, member), {"role": "owner"}, content_type="application/json"
    )

    assert response.status_code == 403
    assert HouseholdMember.objects.get(household=household, user=member).role == "member"


def test_an_owner_hands_the_role_over_and_leaves(household, owner, member):
    client = signed_in(owner)

    promoted = client.patch(
        membership_url(household, member), {"role": "owner"}, content_type="application/json"
    )

    assert promoted.status_code == 200
    assert promoted.json()["role"] == "owner"
    assert client.delete(membership_url(household, owner)).status_code == 204


def test_the_last_owner_neither_steps_down_nor_leaves(household, owner, member):
    client = signed_in(owner)

    demoted = client.patch(
        membership_url(household, owner), {"role": "member"}, content_type="application/json"
    )

    assert demoted.status_code == 409
    assert client.delete(membership_url(household, owner)).status_code == 409
    assert HouseholdMember.objects.get(household=household, user=owner).role == "owner"


def test_a_member_without_a_person_creates_theirs_and_claims_it(household, newcomer):
    client = signed_in(newcomer)

    created = client.post(persons_url(household), {"name": "Alex"}, content_type="application/json")

    assert created.status_code == 201
    claimed = client.post(f"{persons_url(household)}{created.json()['id']}/claim/")
    assert claimed.status_code == 204
    assert household.persons.filter(user=newcomer).exists()


def test_a_member_without_a_person_acts_on_nothing_else(household, newcomer, owner):
    client = signed_in(newcomer)
    camille = f"{persons_url(household)}{household.persons.get(user=owner).pk}/"

    renamed = client.patch(camille, {"name": "Maman"}, content_type="application/json")

    assert renamed.status_code == 403
    assert renamed.json()["detail"] == "Choose which person you are in this household first."
    assert client.delete(camille).status_code == 403
    assert (
        client.patch(
            household_url(household), {"name": "Chez Alex"}, content_type="application/json"
        ).status_code
        == 403
    )
    assert client.delete(household_url(household)).status_code == 403
    assert (
        client.post(
            invitations_url(household),
            {"email": "guest@example.com"},
            content_type="application/json",
        ).status_code
        == 403
    )
    assert (
        client.patch(
            membership_url(household, owner), {"role": "member"}, content_type="application/json"
        ).status_code
        == 403
    )
    assert client.delete(membership_url(household, owner)).status_code == 403


def test_a_member_who_is_nobody_yet_is_not_made_an_owner(household, owner, newcomer):
    response = signed_in(owner).patch(
        membership_url(household, newcomer), {"role": "owner"}, content_type="application/json"
    )

    assert response.status_code == 409
    assert HouseholdMember.objects.get(household=household, user=newcomer).role == "member"


def test_the_two_refusals_do_not_say_the_same_thing(household, member):
    forbidden = signed_in(member).delete(household_url(household))

    assert forbidden.json()["detail"] == "Only an owner of this household can do that."


def test_a_household_of_others_answers_404_rather_than_403(member):
    stranger = User.objects.create_user(username="alex", email="alex@example.com")
    theirs = create_household("Chez les autres", stranger)

    client = signed_in(member)

    assert client.get(persons_url(theirs)).status_code == 404
    assert (
        client.patch(
            household_url(theirs), {"name": "À moi"}, content_type="application/json"
        ).status_code
        == 404
    )


def test_the_owner_role_is_what_creating_a_household_grants(owner):
    created = signed_in(owner).post(
        "/api/households/", {"name": "Chez Camille"}, content_type="application/json"
    )

    household = Household.objects.get(pk=created.json()["id"])
    assert household.members.get(user=owner).role == HouseholdRole.OWNER
