import re
from urllib.parse import unquote

import pytest
from django.conf import settings
from django.core import mail
from django.test import Client

CONFIG_URL = "/api/auth/browser/v1/config"
SIGNUP_URL = "/api/auth/browser/v1/auth/signup"
LOGIN_URL = "/api/auth/browser/v1/auth/login"
SESSION_URL = "/api/auth/browser/v1/auth/session"
VERIFY_EMAIL_URL = "/api/auth/browser/v1/auth/email/verify"
REQUEST_PASSWORD_URL = "/api/auth/browser/v1/auth/password/request"
RESET_PASSWORD_URL = "/api/auth/browser/v1/auth/password/reset"

CREDENTIALS = {"email": "alice@example.com", "password": "an-uncommon-passphrase"}


def key_from_last_email():
    links = re.findall(rf"{settings.FRONTEND_URL}/\S+", mail.outbox[-1].body)
    return unquote(links[-1].rpartition("/")[2])


def sign_up(client):
    client.post(SIGNUP_URL, CREDENTIALS, content_type="application/json")
    client.post(VERIFY_EMAIL_URL, {"key": key_from_last_email()}, content_type="application/json")


@pytest.mark.django_db
def test_the_configuration_endpoint_answers_without_authentication(client):
    response = client.get(CONFIG_URL)

    assert response.status_code == 200
    assert response.json()["data"]["account"]["login_methods"] == ["email"]


@pytest.mark.django_db
def test_the_signup_endpoint_accepts_an_unauthenticated_caller(client, django_user_model):
    response = client.post(SIGNUP_URL, CREDENTIALS, content_type="application/json")

    assert response.status_code == 401
    pending = [flow["id"] for flow in response.json()["data"]["flows"] if flow.get("is_pending")]

    assert pending == ["verify_email"]
    assert django_user_model.objects.get(email="alice@example.com")


@pytest.mark.django_db
def test_the_login_endpoint_rejects_wrong_credentials_rather_than_the_caller(client):
    response = client.post(LOGIN_URL, CREDENTIALS, content_type="application/json")

    assert response.status_code == 400
    assert response.json()["errors"]


@pytest.mark.django_db
def test_the_password_request_endpoint_accepts_an_unauthenticated_caller(client):
    response = client.post(
        REQUEST_PASSWORD_URL, {"email": "alice@example.com"}, content_type="application/json"
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_signing_up_sends_a_verification_email_and_opens_a_session_once_verified(client):
    client.post(SIGNUP_URL, CREDENTIALS, content_type="application/json")

    assert mail.outbox[-1].to == ["alice@example.com"]

    response = client.post(
        VERIFY_EMAIL_URL, {"key": key_from_last_email()}, content_type="application/json"
    )

    assert response.status_code == 200
    assert response.json()["meta"]["is_authenticated"]


@pytest.mark.django_db
def test_the_email_address_is_the_login_identifier(client):
    sign_up(client)
    client.delete(SESSION_URL)

    response = client.post(LOGIN_URL, CREDENTIALS, content_type="application/json")

    assert response.status_code == 200
    assert response.json()["data"]["user"]["email"] == "alice@example.com"


@pytest.mark.django_db
def test_the_session_is_carried_by_a_cookie_and_dropped_by_the_logout(client):
    sign_up(client)

    assert client.cookies["sessionid"]["httponly"]
    assert client.get(SESSION_URL).status_code == 200

    response = client.delete(SESSION_URL)

    assert response.status_code == 401
    assert client.get(SESSION_URL).status_code == 401


@pytest.mark.django_db
def test_the_session_endpoint_refuses_an_anonymous_caller(client):
    response = client.get(SESSION_URL)

    assert response.status_code == 401


@pytest.mark.django_db
def test_a_login_without_the_csrf_token_is_rejected():
    strict_client = Client(enforce_csrf_checks=True)

    response = strict_client.post(LOGIN_URL, CREDENTIALS, content_type="application/json")

    assert response.status_code == 403


@pytest.mark.django_db
def test_a_forgotten_password_is_reset_from_the_emailed_key_without_opening_a_session(client):
    sign_up(client)
    client.delete(SESSION_URL)
    client.post(
        REQUEST_PASSWORD_URL, {"email": "alice@example.com"}, content_type="application/json"
    )

    response = client.post(
        RESET_PASSWORD_URL,
        {"key": key_from_last_email(), "password": "another-uncommon-passphrase"},
        content_type="application/json",
    )

    assert response.status_code == 401
    assert not response.json()["meta"]["is_authenticated"]

    login = client.post(
        LOGIN_URL,
        {"email": "alice@example.com", "password": "another-uncommon-passphrase"},
        content_type="application/json",
    )

    assert login.status_code == 200
