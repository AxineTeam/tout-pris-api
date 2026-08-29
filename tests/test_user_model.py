import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from accounts.models import User


def test_the_project_user_model_is_the_custom_one():
    assert get_user_model() is User


def test_the_custom_user_adds_only_the_language_it_answers_in():
    inherited = {field.name for field in AbstractUser._meta.fields}

    assert {field.name for field in User._meta.fields} == inherited | {"id", "language"}


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


def admin_add_form(data=None):
    from django.contrib import admin

    form_class = admin.site._registry[User].get_form(None, None, change=False)
    return form_class(data=data) if data is not None else form_class()


def test_the_admin_add_form_collects_the_email_address():
    assert "email" in admin_add_form().base_fields


@pytest.mark.django_db
def test_the_admin_add_form_refuses_an_email_already_taken():
    first = admin_add_form(
        {
            "username": "first",
            "email": "shared@example.com",
            "password1": "a-long-enough-password",
            "password2": "a-long-enough-password",
        }
    )
    assert first.is_valid(), first.errors
    first.save()

    second = admin_add_form(
        {
            "username": "second",
            "email": "shared@example.com",
            "password1": "a-long-enough-password",
            "password2": "a-long-enough-password",
        }
    )

    assert not second.is_valid()
    assert "email" in second.errors
