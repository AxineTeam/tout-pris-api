import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_refuse_a_missing_secret_key(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(ValidationError):
        Settings()


def test_settings_refuse_an_empty_secret_key(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "")

    with pytest.raises(ValidationError):
        Settings()
