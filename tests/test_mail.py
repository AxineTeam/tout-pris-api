import json
import logging

import httpx
import pytest
from django.core.mail import EmailMessage, EmailMultiAlternatives

from tout_pris import mail

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


def test_send_email_is_a_logged_no_op_without_api_key(
    brevo_responds, monkeypatch, settings, caplog
):
    requests = brevo_responds(monkeypatch, accepted)
    settings.BREVO_API_KEY = ""

    with caplog.at_level(logging.INFO, logger=mail.logger.name):
        mail.send_email("invitee@example.com", "Welcome", "<p>Hello</p>")

    assert requests == []
    assert "invitee@example.com" in caplog.text


def test_send_email_posts_the_documented_payload_to_brevo(brevo_responds, monkeypatch, settings):
    requests = brevo_responds(monkeypatch, accepted)
    settings.BREVO_API_KEY = "test-key"
    settings.MAIL_FROM_EMAIL = "hello@tout-pris.app"
    settings.MAIL_FROM_NAME = "Tout Pris"

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


def test_send_email_applies_the_timeout_to_the_request(brevo_responds, monkeypatch, settings):
    requests = brevo_responds(monkeypatch, accepted)
    settings.BREVO_API_KEY = "test-key"

    mail.send_email("invitee@example.com", "Welcome", "<p>Hello</p>")

    assert requests[0].extensions["timeout"]["read"] == mail.BREVO_TIMEOUT_SECONDS


def test_send_email_logs_a_rejection_instead_of_raising(
    brevo_responds, monkeypatch, settings, caplog
):
    brevo_responds(monkeypatch, lambda request: httpx.Response(400, json=REJECTED_RESPONSE))
    settings.BREVO_API_KEY = "test-key"

    with caplog.at_level(logging.ERROR, logger=mail.logger.name):
        mail.send_email("invitee@example.com", "Welcome", "<p>Hello</p>")

    assert "invitee@example.com" in caplog.text


def test_send_email_logs_a_transport_failure_instead_of_raising(
    brevo_responds, monkeypatch, settings, caplog
):
    def time_out(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("brevo took too long", request=request)

    brevo_responds(monkeypatch, time_out)
    settings.BREVO_API_KEY = "test-key"

    with caplog.at_level(logging.ERROR, logger=mail.logger.name):
        mail.send_email("invitee@example.com", "Welcome", "<p>Hello</p>")

    assert "invitee@example.com" in caplog.text


def test_send_email_logs_an_unparsable_response_instead_of_raising(
    brevo_responds, monkeypatch, settings, caplog
):
    brevo_responds(monkeypatch, lambda request: httpx.Response(201, text="not json at all"))
    settings.BREVO_API_KEY = "test-key"

    with caplog.at_level(logging.ERROR, logger=mail.logger.name):
        mail.send_email("invitee@example.com", "Welcome", "<p>Hello</p>")

    assert "invitee@example.com" in caplog.text


def test_the_backend_sends_the_text_body_of_a_django_message(brevo_responds, monkeypatch, settings):
    requests = brevo_responds(monkeypatch, accepted)
    settings.BREVO_API_KEY = "test-key"
    message = EmailMessage(
        subject="Confirm your email",
        body="Go to https://example.com/key",
        to=["invitee@example.com"],
    )

    sent = mail.BrevoEmailBackend().send_messages([message])

    assert sent == 1
    assert json.loads(requests[0].content)["textContent"] == "Go to https://example.com/key"
    assert "htmlContent" not in json.loads(requests[0].content)


def test_the_backend_prefers_the_html_alternative_of_a_django_message(
    brevo_responds, monkeypatch, settings
):
    requests = brevo_responds(monkeypatch, accepted)
    settings.BREVO_API_KEY = "test-key"
    message = EmailMultiAlternatives(
        subject="Confirm your email",
        body="Go to https://example.com/key",
        to=["invitee@example.com"],
    )
    message.attach_alternative("<p>Go to https://example.com/key</p>", "text/html")

    mail.BrevoEmailBackend().send_messages([message])

    payload = json.loads(requests[0].content)
    assert payload["htmlContent"] == "<p>Go to https://example.com/key</p>"
    assert payload["textContent"] == "Go to https://example.com/key"


def test_the_backend_sends_one_email_per_recipient(brevo_responds, monkeypatch, settings):
    requests = brevo_responds(monkeypatch, accepted)
    settings.BREVO_API_KEY = "test-key"
    message = EmailMessage(
        subject="Confirm your email",
        body="Go to https://example.com/key",
        to=["invitee@example.com", "partner@example.com"],
    )

    mail.BrevoEmailBackend().send_messages([message])

    assert [json.loads(request.content)["to"][0]["email"] for request in requests] == [
        "invitee@example.com",
        "partner@example.com",
    ]
