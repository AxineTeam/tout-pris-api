import pytest
from django.test import Client

from accounts.models import User
from tests.test_authentication import CREDENTIALS, LOGIN_URL, SESSION_URL, SIGNUP_URL, sign_up

pytestmark = pytest.mark.django_db

HOUSEHOLDS_URL = "/api/households/"
ME_URL = "/api/me/"


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


def test_an_account_reads_the_language_it_is_answered_in_from_its_session(alice):
    alice.language = "fr"
    alice.save()

    response = signed_in_client(alice).get(SESSION_URL)

    assert response.json()["data"]["user"]["language"] == "fr"


def test_an_account_chooses_the_language_it_is_answered_in(alice):
    client = signed_in_client(alice)

    response = client.patch(ME_URL, {"language": "fr"}, content_type="application/json")

    assert response.status_code == 200
    assert response.json() == {"id": alice.pk, "email": alice.email, "language": "fr"}
    assert client.get(SESSION_URL).json()["data"]["user"]["language"] == "fr"


def test_a_language_nobody_speaks_here_is_refused(alice):
    response = signed_in_client(alice).patch(
        ME_URL, {"language": "de"}, content_type="application/json"
    )

    assert response.status_code == 400
    assert User.objects.get(pk=alice.pk).language == "en-us"


def test_choosing_a_language_needs_an_account(client):
    response = client.patch(ME_URL, {"language": "fr"}, content_type="application/json")

    assert response.status_code == 401


def test_the_chosen_language_outlives_the_session_it_was_chosen_in(client):
    sign_up(client)
    client.patch(ME_URL, {"language": "fr"}, content_type="application/json")
    client.delete(SESSION_URL)

    client.post(LOGIN_URL, CREDENTIALS, content_type="application/json")
    response = client.get(HOUSEHOLDS_URL, headers={"accept-language": "en-US"})

    assert response.headers["Content-Language"] == "fr"
