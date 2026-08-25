import pytest

from accounts.models import User

PASSWORD = "correct-horse-battery-staple"


@pytest.fixture
def administrator(db):
    return User.objects.create_superuser(
        username="root", email="root@example.com", password=PASSWORD
    )


@pytest.fixture
def ordinary_account(db):
    return User.objects.create_user(
        username="camille", email="camille@example.com", password=PASSWORD
    )


@pytest.fixture(autouse=True)
def a_published_build(settings):
    settings.APP_VERSION = "v1.2.0"
    settings.APP_COMMIT = "7e6cfdc"


def test_health_reports_the_service_as_up(client):
    response = client.get("/api/health/")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_tells_an_administrator_the_exact_build(client, administrator):
    client.force_login(administrator)

    response = client.get("/api/health/")

    assert response.json() == {"status": "ok", "version": "v1.2.0", "commit": "7e6cfdc"}


def test_health_tells_an_ordinary_account_the_ref_but_not_the_commit(client, ordinary_account):
    client.force_login(ordinary_account)

    response = client.get("/api/health/")

    assert response.json() == {"status": "ok", "version": "v1.2.0", "commit": None}


def test_health_tells_an_anonymous_caller_the_ref_but_not_the_commit(client):
    response = client.get("/api/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "v1.2.0", "commit": None}


def test_the_generated_docs_are_served_under_the_api_prefix(client):
    response = client.get("/api/docs/")

    assert response.status_code == 200


def test_the_generated_schema_describes_the_health_operation(client):
    schema = client.get("/api/schema/?format=json").json()

    assert schema["paths"]["/api/health/"]["get"]["summary"] == "Health check"
