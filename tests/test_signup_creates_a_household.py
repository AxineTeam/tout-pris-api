import json
import time
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
import requests
from allauth.account.models import EmailAddress
from django.test import Client

from households.models import Household, HouseholdMember, HouseholdRole, Person
from tests.test_authentication import SIGNUP_URL, sign_up

PROVIDER_REDIRECT_URL = "/api/auth/browser/v1/auth/provider/redirect"
GOOGLE_CALLBACK_URL = "/accounts/google/login/callback/"
GOOGLE_CLIENT_ID = "a-google-client-id"


@pytest.fixture
def google_app(settings):
    settings.SOCIALACCOUNT_PROVIDERS = {
        "google": {
            "APP": {"client_id": GOOGLE_CLIENT_ID, "secret": "a-google-secret"},
            "SCOPE": ["profile", "email"],
        }
    }


@pytest.fixture
def google_answers(monkeypatch):
    def install(email, first_name, last_name):
        identity = {
            "iss": "https://accounts.google.com",
            "aud": GOOGLE_CLIENT_ID,
            "sub": "the-google-account-id",
            "exp": int(time.time()) + 300,
            "iat": int(time.time()),
            "email": email,
            "email_verified": True,
            "given_name": first_name,
            "family_name": last_name,
        }
        payload = {
            "access_token": "a-google-access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "id_token": jwt.encode(
                identity, "the-callback-skips-the-signature-check", algorithm="HS256"
            ),
        }

        def answer(session, method, url, **kwargs):
            response = requests.Response()
            response.status_code = 200
            response.url = url
            response.headers["Content-Type"] = "application/json"
            response._content = json.dumps(payload).encode()
            return response

        monkeypatch.setattr(requests.Session, "request", answer)

    return install


def sign_up_with_google(client):
    redirect = client.post(
        PROVIDER_REDIRECT_URL,
        {"provider": "google", "callback_url": "/", "process": "login"},
    )
    state = parse_qs(urlparse(redirect["Location"]).query)["state"][0]
    return client.get(GOOGLE_CALLBACK_URL, {"code": "a-google-authorization-code", "state": state})


@pytest.mark.django_db
def test_signing_up_by_email_creates_the_household_the_membership_and_the_person(client):
    sign_up(client)

    household = Household.objects.get()
    membership = HouseholdMember.objects.get()
    person = Person.objects.get()

    assert household.name == "alice"
    assert membership.household == household
    assert membership.user.email == "alice@example.com"
    assert membership.role == HouseholdRole.OWNER
    assert person.household == household
    assert person.user == membership.user
    assert person.name == "alice"


@pytest.mark.django_db
def test_signing_up_through_a_provider_creates_the_household_the_membership_and_the_person(
    client, google_app, google_answers, django_user_model
):
    google_answers("bob@example.com", "Bob", "Martin")

    response = sign_up_with_google(client)

    assert response.status_code == 302
    user = django_user_model.objects.get(email="bob@example.com")
    assert EmailAddress.objects.get(user=user).verified
    household = Household.objects.get()
    assert household.name == "Bob Martin"
    assert HouseholdMember.objects.get(user=user).household == household
    assert Person.objects.get(user=user).household == household


@pytest.mark.django_db
def test_signing_in_again_through_a_provider_reuses_the_existing_household(
    client, google_app, google_answers
):
    google_answers("bob@example.com", "Bob", "Martin")
    sign_up_with_google(client)
    client.delete("/api/auth/browser/v1/auth/session")

    sign_up_with_google(client)

    assert Household.objects.count() == 1
    assert Person.objects.count() == 1


@pytest.mark.django_db
def test_each_account_only_reaches_the_household_of_its_own_signup(
    client, django_user_model, google_app, google_answers
):
    sign_up(client)
    google_answers("bob@example.com", "Bob", "Martin")
    sign_up_with_google(Client())

    alice = django_user_model.objects.get(email="alice@example.com")
    bob = django_user_model.objects.get(email="bob@example.com")

    assert Household.objects.count() == 2
    assert not Household.objects.filter(members__user=alice, persons__user=bob).exists()
    assert list(Person.objects.filter(household__members__user=alice)) == [
        Person.objects.get(user=alice)
    ]


@pytest.mark.django_db
def test_an_email_already_taken_does_not_create_a_second_household(client):
    sign_up(client)

    client.post(
        SIGNUP_URL,
        {"email": "alice@example.com", "password": "yet-another-passphrase"},
        content_type="application/json",
    )

    assert Household.objects.count() == 1
