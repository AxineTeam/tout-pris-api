import json
import logging

import httpx
import pytest

from app import mail
from app.config import Settings

BREVO_ENDPOINT = "https://api.brevo.com/v3/smtp/email"
ACCEPTED_RESPONSE = {"messageId": "<202608191600.12345@smtp-relay.brevo.com>"}
REJECTED_RESPONSE = {"code": "invalid_parameter", "message": "sender is not valid"}


@pytest.fixture
def brevo_responds():
    def install(monkeypatch, handler):
        requests = []

        def handle_request(
            transport: httpx.HTTPTransport, request: httpx.Request
        ) -> httpx.Response:
            requests.append(request)
            return handler(request)

        monkeypatch.setattr(httpx.HTTPTransport, "handle_request", handle_request)
        return requests

    return install


def accepted(request: httpx.Request) -> httpx.Response:
    return httpx.Response(201, json=ACCEPTED_RESPONSE)


def test_send_email_is_a_logged_no_op_without_api_key(brevo_responds, monkeypatch, caplog):
    requests = brevo_responds(monkeypatch, accepted)
    monkeypatch.setattr(mail.settings, "brevo_api_key", "")

    with caplog.at_level(logging.INFO, logger=mail.logger.name):
        mail.send_email("invitee@example.com", "Welcome", "<p>Hello</p>")

    assert requests == []
    assert "invitee@example.com" in caplog.text


def test_send_email_posts_the_documented_payload_to_brevo(brevo_responds, monkeypatch):
    requests = brevo_responds(monkeypatch, accepted)
    monkeypatch.setattr(mail.settings, "brevo_api_key", "test-key")
    monkeypatch.setattr(mail.settings, "mail_from_email", "hello@tout-pris.app")
    monkeypatch.setattr(mail.settings, "mail_from_name", "Tout Pris")

    mail.send_email("invitee@example.com", "Welcome", "<p>Hello</p>")

    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert str(request.url) == BREVO_ENDPOINT
    assert request.headers["api-key"] == "test-key"
    assert json.loads(request.content) == {
        "sender": {"email": "hello@tout-pris.app", "name": "Tout Pris"},
        "to": [{"email": "invitee@example.com"}],
        "subject": "Welcome",
        "htmlContent": "<p>Hello</p>",
    }


def test_send_email_applies_the_timeout_to_the_request(brevo_responds, monkeypatch):
    requests = brevo_responds(monkeypatch, accepted)
    monkeypatch.setattr(mail.settings, "brevo_api_key", "test-key")

    mail.send_email("invitee@example.com", "Welcome", "<p>Hello</p>")

    assert requests[0].extensions["timeout"]["read"] == mail.BREVO_TIMEOUT_SECONDS


def test_send_email_logs_a_rejection_instead_of_raising(brevo_responds, monkeypatch, caplog):
    brevo_responds(monkeypatch, lambda request: httpx.Response(400, json=REJECTED_RESPONSE))
    monkeypatch.setattr(mail.settings, "brevo_api_key", "test-key")

    with caplog.at_level(logging.ERROR, logger=mail.logger.name):
        mail.send_email("invitee@example.com", "Welcome", "<p>Hello</p>")

    assert "invitee@example.com" in caplog.text


def test_send_email_logs_a_transport_failure_instead_of_raising(
    brevo_responds, monkeypatch, caplog
):
    def time_out(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("brevo took too long", request=request)

    brevo_responds(monkeypatch, time_out)
    monkeypatch.setattr(mail.settings, "brevo_api_key", "test-key")

    with caplog.at_level(logging.ERROR, logger=mail.logger.name):
        mail.send_email("invitee@example.com", "Welcome", "<p>Hello</p>")

    assert "invitee@example.com" in caplog.text


def test_send_email_logs_an_unparsable_response_instead_of_raising(
    brevo_responds, monkeypatch, caplog
):
    brevo_responds(monkeypatch, lambda request: httpx.Response(201, text="not json at all"))
    monkeypatch.setattr(mail.settings, "brevo_api_key", "test-key")

    with caplog.at_level(logging.ERROR, logger=mail.logger.name):
        mail.send_email("invitee@example.com", "Welcome", "<p>Hello</p>")

    assert "invitee@example.com" in caplog.text


def test_settings_default_to_a_disabled_brevo_client(monkeypatch):
    monkeypatch.delenv("BREVO_API_KEY", raising=False)

    assert Settings().brevo_api_key == ""


def test_settings_read_the_environment(monkeypatch):
    monkeypatch.setenv("BREVO_API_KEY", "from-env")
    monkeypatch.setenv("MAIL_FROM_EMAIL", "sender@example.com")
    monkeypatch.setenv("MAIL_FROM_NAME", "Sender")

    settings = Settings()

    assert settings.brevo_api_key == "from-env"
    assert settings.mail_from_email == "sender@example.com"
    assert settings.mail_from_name == "Sender"
