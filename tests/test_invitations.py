import datetime
import hashlib
import re

import pytest
from django.conf import settings
from django.core import mail
from django.test import Client
from django.utils import timezone

from accounts.models import User
from households.models import Household, HouseholdMember, Invitation, Person
from tests.test_authentication import SIGNUP_URL, VERIFY_EMAIL_URL, key_from_last_email

pytestmark = pytest.mark.django_db

ACCEPT_URL = "/api/invitations/accept/"
GUEST_EMAIL = "guest@example.com"


def token_from_last_email():
    prefix = settings.INVITATION_FRONTEND_URL.format(key="")
    return re.findall(rf"{prefix}(\S+)", mail.outbox[-1].body)[-1]


def invitations_url(household):
    return f"/api/households/{household.pk}/invitations/"


@pytest.fixture
def member():
    user = User.objects.create_user(
        username="camille", email="camille@example.com", first_name="Camille"
    )
    household = Household.objects.create(name="Famille Martin")
    HouseholdMember.objects.create(household=household, user=user)
    Person.objects.create(household=household, user=user, name="Camille")
    return user, household


@pytest.fixture
def signed_in(member):
    user, household = member
    client = Client()
    client.force_login(user)
    return client, household


@pytest.fixture
def send_invitation(signed_in, django_capture_on_commit_callbacks):
    client, household = signed_in

    def post(email=GUEST_EMAIL, **extra):
        with django_capture_on_commit_callbacks(execute=True):
            return client.post(
                invitations_url(household),
                {"email": email, **extra},
                content_type="application/json",
            )

    return post


@pytest.fixture
def guest():
    return User.objects.create_user(username="sacha", email=GUEST_EMAIL, first_name="Sacha")


def signed_in_client(user):
    client = Client()
    client.force_login(user)
    return client


def test_inviting_an_address_sends_it_a_link_holding_the_token(send_invitation):
    response = send_invitation()

    assert response.status_code == 204
    assert [message.to for message in mail.outbox] == [[GUEST_EMAIL]]
    assert (
        Invitation.objects.get().token_hash
        == hashlib.sha256(token_from_last_email().encode()).hexdigest()
    )


def test_the_invitation_expires_a_week_after_it_was_sent(send_invitation):
    send_invitation()

    invitation = Invitation.objects.get()
    lifetime = invitation.expires_at - invitation.created_at
    assert round(lifetime.total_seconds()) == datetime.timedelta(days=7).total_seconds()


def test_an_address_without_an_account_is_told_to_create_one(send_invitation):
    send_invitation()

    assert "Create your account" in mail.outbox[0].body


def test_an_address_with_an_account_is_told_to_sign_in(send_invitation, guest):
    send_invitation()

    assert "Sign in" in mail.outbox[0].body


def test_the_answer_does_not_say_whether_the_address_has_an_account(
    send_invitation, signed_in, django_capture_on_commit_callbacks, guest
):
    client, household = signed_in

    with_account = send_invitation(email=GUEST_EMAIL)
    without_account = send_invitation(email="nobody@example.com")

    assert with_account.status_code == without_account.status_code
    assert with_account.content == without_account.content == b""


def test_inviting_a_member_of_the_household_again_creates_nothing(send_invitation, member):
    user, _ = member

    response = send_invitation(email=user.email)

    assert response.status_code == 204
    assert not Invitation.objects.exists()
    assert mail.outbox == []


def test_inviting_the_same_address_again_replaces_the_pending_invitation(send_invitation):
    send_invitation()
    first = token_from_last_email()

    send_invitation()

    assert Invitation.objects.count() == 1
    assert token_from_last_email() != first


def test_a_pending_invitation_is_listed_for_its_household(send_invitation, signed_in):
    client, household = signed_in
    send_invitation()

    listed = client.get(invitations_url(household)).json()

    assert [invitation["email"] for invitation in listed] == [GUEST_EMAIL]


def test_a_cancelled_invitation_stops_being_listed(send_invitation, signed_in):
    client, household = signed_in
    send_invitation()
    invitation = Invitation.objects.get()

    response = client.delete(f"{invitations_url(household)}{invitation.pk}/")

    assert response.status_code == 204
    assert client.get(invitations_url(household)).json() == []


def test_the_invitations_of_another_household_are_out_of_reach(signed_in):
    client, _ = signed_in
    stranger = Household.objects.create(name="Chez les autres")

    assert client.get(invitations_url(stranger)).status_code == 404
    assert client.post(invitations_url(stranger), {"email": GUEST_EMAIL}).status_code == 404


def test_accepting_makes_the_guest_a_member_of_the_household(send_invitation, signed_in, guest):
    _, household = signed_in
    send_invitation()
    token = token_from_last_email()

    response = signed_in_client(guest).post(
        ACCEPT_URL, {"token": token}, content_type="application/json"
    )

    assert response.status_code == 200
    assert response.json() == {"id": household.pk, "name": household.name, "personal": False}
    assert HouseholdMember.objects.filter(household=household, user=guest).exists()
    assert household.persons.filter(user=guest).exists()


def test_accepting_spends_the_token(send_invitation, guest):
    send_invitation()
    token = token_from_last_email()
    client = signed_in_client(guest)
    client.post(ACCEPT_URL, {"token": token}, content_type="application/json")

    response = client.post(ACCEPT_URL, {"token": token}, content_type="application/json")

    assert response.status_code == 404


def test_an_unknown_token_is_refused(guest):
    response = signed_in_client(guest).post(
        ACCEPT_URL, {"token": "a-token-nobody-issued"}, content_type="application/json"
    )

    assert response.status_code == 404


def test_an_expired_token_is_refused(send_invitation, guest):
    send_invitation()
    token = token_from_last_email()
    invitation = Invitation.objects.get()
    invitation.expires_at = timezone.now() - datetime.timedelta(seconds=1)
    invitation.save()

    response = signed_in_client(guest).post(
        ACCEPT_URL, {"token": token}, content_type="application/json"
    )

    assert response.status_code == 404


def test_accepting_fills_in_the_person_the_guest_was_expected_to_be(
    send_invitation, signed_in, guest
):
    _, household = signed_in
    waiting = Person.objects.create(household=household, name="Sacha")
    send_invitation(person=waiting.pk)
    token = token_from_last_email()

    signed_in_client(guest).post(ACCEPT_URL, {"token": token}, content_type="application/json")

    waiting.refresh_from_db()
    assert waiting.user == guest
    assert household.persons.filter(user=guest).count() == 1


def test_a_person_of_another_household_is_refused_like_one_that_does_not_exist(send_invitation):
    stranger = Person.objects.create(
        household=Household.objects.create(name="Chez les autres"), name="Inconnu"
    )

    missing = stranger.pk + 10_000

    refused = send_invitation(person=stranger.pk)
    unknown = send_invitation(person=missing)

    assert refused.status_code == unknown.status_code == 400
    assert refused.json() == {"person": [f'Invalid pk "{stranger.pk}" - object does not exist.']}
    assert unknown.json() == {"person": [f'Invalid pk "{missing}" - object does not exist.']}
    assert not Invitation.objects.exists()


def test_the_token_is_never_stored(send_invitation):
    send_invitation()

    stored = Invitation.objects.values().get()

    assert token_from_last_email() not in str(stored)


def test_a_member_who_accepts_again_stays_a_single_member(send_invitation, signed_in, member):
    user, household = member
    send_invitation()
    token = token_from_last_email()

    response = signed_in_client(user).post(
        ACCEPT_URL, {"token": token}, content_type="application/json"
    )

    assert response.status_code == 200
    assert HouseholdMember.objects.filter(household=household, user=user).count() == 1


def sign_up_the_guest():
    client = Client()
    client.post(
        SIGNUP_URL,
        {"email": GUEST_EMAIL, "password": "an-uncommon-passphrase"},
        content_type="application/json",
    )
    client.post(VERIFY_EMAIL_URL, {"key": key_from_last_email()}, content_type="application/json")
    return client


def test_a_guest_who_signs_up_to_answer_keeps_their_personal_household(send_invitation, signed_in):
    _, household = signed_in
    send_invitation()
    token = token_from_last_email()
    client = sign_up_the_guest()

    client.post(ACCEPT_URL, {"token": token}, content_type="application/json")

    guest = User.objects.get(email=GUEST_EMAIL)
    assert set(Household.objects.filter(members__user=guest)) == {
        guest.personal_household,
        household,
    }


def test_a_guest_who_already_had_a_shared_household_keeps_it(send_invitation, signed_in, guest):
    _, household = signed_in
    own = Household.objects.create(name="Chez Sacha")
    HouseholdMember.objects.create(household=own, user=guest)
    Person.objects.create(household=own, user=guest, name="Sacha")
    send_invitation()
    token = token_from_last_email()

    signed_in_client(guest).post(ACCEPT_URL, {"token": token}, content_type="application/json")

    assert set(Household.objects.filter(members__user=guest)) == {own, household}


def test_the_invitation_endpoints_refuse_an_unauthenticated_caller(member):
    _, household = member
    client = Client()

    assert client.get(invitations_url(household)).status_code == 401
    assert client.post(ACCEPT_URL, {"token": "any"}).status_code == 401


def test_sending_invitations_is_rate_limited(signed_in, django_capture_on_commit_callbacks):
    client, household = signed_in

    with django_capture_on_commit_callbacks(execute=True):
        answers = [
            client.post(
                invitations_url(household),
                {"email": f"guest{index}@example.com"},
                content_type="application/json",
            ).status_code
            for index in range(21)
        ]

    assert answers[:20] == [204] * 20
    assert answers[20] == 429


def test_a_personal_household_has_no_invitations_to_speak_of(member):
    user, _ = member
    personal = Household.objects.create(name="camille", personal_of=user)
    personal.members.create(user=user)
    client = signed_in_client(user)

    assert client.get(invitations_url(personal)).status_code == 404
    assert (
        client.post(
            invitations_url(personal), {"email": GUEST_EMAIL}, content_type="application/json"
        ).status_code
        == 404
    )
