import importlib.util
import pathlib

import pytest
from django.core.exceptions import ImproperlyConfigured

SETTINGS_PATH = pathlib.Path(__file__).resolve().parent.parent / "tout_pris" / "settings.py"


def load_settings(monkeypatch, **environment):
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    spec = importlib.util.spec_from_file_location("settings_under_test", SETTINGS_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_production_refuses_the_development_secret_key(monkeypatch):
    monkeypatch.delenv("DJANGO_SECRET_KEY", raising=False)

    with pytest.raises(ImproperlyConfigured):
        load_settings(monkeypatch, DJANGO_DEBUG="false")


def test_production_serves_the_static_files_from_the_manifest(monkeypatch):
    settings = load_settings(
        monkeypatch, DJANGO_DEBUG="false", DJANGO_SECRET_KEY="a-real-production-secret-key"
    )

    assert "whitenoise" in settings.STORAGES["staticfiles"]["BACKEND"]


def test_production_secures_the_cookies_and_the_transport(monkeypatch):
    settings = load_settings(
        monkeypatch, DJANGO_DEBUG="false", DJANGO_SECRET_KEY="a-real-production-secret-key"
    )

    assert settings.SESSION_COOKIE_SECURE
    assert settings.CSRF_COOKIE_SECURE
    assert settings.SECURE_SSL_REDIRECT
    assert settings.SECURE_HSTS_SECONDS > 0


def test_development_leaves_the_transport_settings_alone(monkeypatch):
    settings = load_settings(monkeypatch, DJANGO_DEBUG="true")

    assert not hasattr(settings, "SECURE_SSL_REDIRECT")


def test_a_brevo_key_sends_the_emails_through_brevo(monkeypatch):
    settings = load_settings(monkeypatch, BREVO_API_KEY="a-real-key", EMAIL_HOST="mailpit")

    assert settings.MAILERS["default"]["BACKEND"] == "tout_pris.mail.BrevoEmailBackend"


def test_an_smtp_host_sends_the_emails_to_the_local_collector(monkeypatch):
    settings = load_settings(monkeypatch, BREVO_API_KEY="", EMAIL_HOST="mailpit", EMAIL_PORT="1025")

    assert settings.MAILERS["default"] == {
        "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "OPTIONS": {"host": "mailpit", "port": 1025},
    }


def test_without_any_mail_configuration_the_emails_are_printed(monkeypatch):
    settings = load_settings(monkeypatch, BREVO_API_KEY="", EMAIL_HOST="")

    assert (
        settings.MAILERS["default"]["BACKEND"] == "django.core.mail.backends.console.EmailBackend"
    )


def test_a_reader_is_not_locked_out_while_another_request_writes(monkeypatch):
    settings = load_settings(monkeypatch)

    assert settings.DATABASES["default"]["OPTIONS"]["init_command"] == (
        "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;"
    )


def test_a_writer_takes_its_lock_at_once_and_queues_instead_of_failing(monkeypatch):
    settings = load_settings(monkeypatch)

    assert settings.DATABASES["default"]["OPTIONS"]["transaction_mode"] == "IMMEDIATE"
    assert settings.DATABASES["default"]["OPTIONS"]["timeout"] == 5
