import pytest

from accounts.models import User

ADMIN_PASSWORD = "correct-horse-battery-staple"


@pytest.fixture
def administrator(db):
    return User.objects.create_superuser(
        username="root", email="root@example.com", password=ADMIN_PASSWORD
    )


@pytest.fixture
def ordinary_account(db):
    return User.objects.create_user(
        username="camille", email="camille@example.com", password=ADMIN_PASSWORD
    )


def test_health_reports_the_service_as_up(client):
    response = client.get("/api/health/")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_tells_an_administrator_which_version_is_running(client, administrator, settings):
    settings.APP_VERSION = "v1.2.0"
    client.force_login(administrator)

    response = client.get("/api/health/")

    assert response.json()["version"] == "v1.2.0"


def test_health_keeps_the_version_from_an_ordinary_account(client, ordinary_account, settings):
    settings.APP_VERSION = "v1.2.0"
    client.force_login(ordinary_account)

    response = client.get("/api/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": None}


def test_health_keeps_the_version_from_an_anonymous_caller(client, settings):
    settings.APP_VERSION = "v1.2.0"

    response = client.get("/api/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": None}


def test_the_version_falls_back_to_dev_outside_a_published_image(client, administrator):
    client.force_login(administrator)

    response = client.get("/api/health/")

    assert response.json()["version"] == "dev"


def test_the_generated_docs_are_served_under_the_api_prefix(client):
    response = client.get("/api/docs/")

    assert response.status_code == 200


def test_the_generated_schema_describes_the_health_operation(client):
    schema = client.get("/api/schema/?format=json").json()

    assert schema["paths"]["/api/health/"]["get"]["summary"] == "Health check"
