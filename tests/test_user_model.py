import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from accounts.models import User


def test_the_project_user_model_is_the_custom_one():
    assert get_user_model() is User


def test_the_custom_user_adds_no_field_of_its_own():
    inherited = {field.name for field in AbstractUser._meta.fields}

    assert {field.name for field in User._meta.fields} == inherited | {"id"}


@pytest.mark.django_db
def test_a_user_can_be_created_with_a_usable_password():
    user = User.objects.create_user(username="alice", email="alice@example.com", password="s3cret")

    assert user.check_password("s3cret")
    assert User.objects.get(username="alice") == user


@pytest.mark.django_db
def test_an_email_address_identifies_a_single_account():
    User.objects.create_user(username="alice", email="alice@example.com")

    with pytest.raises(IntegrityError):
        User.objects.create_user(username="alice-again", email="alice@example.com")


@pytest.mark.django_db
def test_an_account_without_an_email_address_is_invalid():
    with pytest.raises(ValidationError) as invalid:
        User(username="alice", password="s3cret").full_clean()

    assert "email" in invalid.value.error_dict
