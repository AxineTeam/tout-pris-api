import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser

from accounts.models import User


def test_the_project_user_model_is_the_custom_one():
    assert get_user_model() is User


def test_the_custom_user_declares_no_field_of_its_own():
    inherited = {field.name for field in AbstractUser._meta.fields}

    assert {field.name for field in User._meta.fields} == inherited | {"id"}


@pytest.mark.django_db
def test_a_user_can_be_created_with_a_usable_password():
    user = User.objects.create_user(username="alice", email="alice@example.com", password="s3cret")

    assert user.check_password("s3cret")
    assert User.objects.get(username="alice") == user
