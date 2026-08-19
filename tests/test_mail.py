import logging
from unittest.mock import MagicMock

import httpx
import pytest
from brevo.core.api_error import ApiError

from app import mail
from app.config import Settings


@pytest.fixture
def brevo(monkeypatch):
    client_class = MagicMock()
    monkeypatch.setattr(mail, "Brevo", client_class)
    return client_class


def test_send_email_is_a_logged_no_op_without_api_key(brevo, monkeypatch, caplog):
    monkeypatch.setattr(mail.settings, "brevo_api_key", "")

    with caplog.at_level(logging.INFO, logger=mail.logger.name):
        mail.send_email("invitee@example.com", "Welcome", "<p>Hello</p>")

    brevo.assert_not_called()
    assert "invitee@example.com" in caplog.text


def test_send_email_calls_brevo_with_the_configured_sender(brevo, monkeypatch):
    monkeypatch.setattr(mail.settings, "brevo_api_key", "test-key")
    monkeypatch.setattr(mail.settings, "mail_from_email", "hello@tout-pris.app")
    monkeypatch.setattr(mail.settings, "mail_from_name", "Tout Pris")

    mail.send_email("invitee@example.com", "Welcome", "<p>Hello</p>")

    brevo.assert_called_once()
    http_client = brevo.call_args.kwargs["httpx_client"]
    assert brevo.call_args.kwargs["api_key"] == "test-key"
    assert http_client.timeout.read == mail.BREVO_TIMEOUT_SECONDS
    assert http_client.is_closed
    send = brevo.return_value.transactional_emails.send_transac_email
    send.assert_called_once()
    payload = send.call_args.kwargs
    assert payload["sender"].email == "hello@tout-pris.app"
    assert payload["sender"].name == "Tout Pris"
    assert [item.email for item in payload["to"]] == ["invitee@example.com"]
    assert payload["subject"] == "Welcome"
    assert payload["html_content"] == "<p>Hello</p>"


def test_send_email_logs_api_errors_instead_of_raising(brevo, monkeypatch, caplog):
    monkeypatch.setattr(mail.settings, "brevo_api_key", "test-key")
    brevo.return_value.transactional_emails.send_transac_email.side_effect = ApiError(
        status_code=400, body="invalid sender"
    )

    with caplog.at_level(logging.ERROR, logger=mail.logger.name):
        mail.send_email("invitee@example.com", "Welcome", "<p>Hello</p>")

    assert "invitee@example.com" in caplog.text


def test_send_email_logs_unexpected_failures_instead_of_raising(brevo, monkeypatch, caplog):
    monkeypatch.setattr(mail.settings, "brevo_api_key", "test-key")
    brevo.return_value.transactional_emails.send_transac_email.side_effect = httpx.ReadTimeout(
        "brevo took too long"
    )

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
