import pytest
from django.test import Client

from accounts.models import User
from tests.test_authentication import CREDENTIALS, SIGNUP_URL

pytestmark = pytest.mark.django_db

HOUSEHOLDS_URL = "/api/households/"


@pytest.fixture
def alice():
    return User.objects.create_user(username="alice", email="alice@example.com")


def signed_in_client(user):
    client = Client()
    client.force_login(user)
    return client


def test_the_language_of_the_account_beats_the_one_the_browser_asks_for(alice):
    alice.language = "fr"
    alice.save()

    response = signed_in_client(alice).post(
        HOUSEHOLDS_URL, {}, content_type="application/json", headers={"accept-language": "en-US"}
    )

    assert response.status_code == 400
    assert response.json() == {"name": ["Ce champ est obligatoire."]}
    assert response.headers["Content-Language"] == "fr"


def test_a_caller_without_an_account_is_answered_in_the_language_they_ask_for(client):
    response = client.get(HOUSEHOLDS_URL, headers={"accept-language": "fr"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Informations d'authentification non fournies."}
    assert response.headers["Content-Language"] == "fr"


def test_the_language_of_a_response_is_announced_as_varying_on_both_the_session_and_the_header(
    client,
):
    response = client.get(HOUSEHOLDS_URL)

    assert set(response.headers["Vary"].split(", ")) >= {"Accept-Language", "Cookie"}


def test_a_new_account_starts_in_the_language_its_browser_asked_for(client):
    client.post(
        SIGNUP_URL, CREDENTIALS, content_type="application/json", headers={"accept-language": "fr"}
    )

    assert User.objects.get(email=CREDENTIALS["email"]).language == "fr"


def test_a_new_account_falls_back_to_english_when_its_browser_asks_for_nothing_known(client):
    client.post(
        SIGNUP_URL, CREDENTIALS, content_type="application/json", headers={"accept-language": "de"}
    )

    assert User.objects.get(email=CREDENTIALS["email"]).language == "en-us"
