import pytest


@pytest.mark.django_db
def test_the_domain_schema_describes_the_health_operation(client):
    schema = client.get("/api/schema/?format=json").json()

    assert schema["paths"]["/api/health/"]["get"]["summary"] == "Health check"


@pytest.mark.django_db
def test_the_domain_schema_leaves_the_authentication_endpoints_to_allauth(client):
    schema = client.get("/api/schema/?format=json").json()

    assert not [path for path in schema["paths"] if path.startswith("/api/auth/")]


@pytest.mark.django_db
def test_allauth_serves_its_own_specification(client):
    schema = client.get("/api/auth/openapi.json").json()

    assert "/auth/signup" in "".join(schema["paths"])
