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
