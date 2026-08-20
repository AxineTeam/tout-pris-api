import pytest
from django.core.exceptions import ImproperlyConfigured

from tout_pris.schema import merge_without_overwriting


def test_the_generated_schema_describes_the_authentication_endpoints(client):
    schema = client.get("/api/schema/?format=json").json()

    assert "/api/auth/browser/v1/auth/login" in schema["paths"]
    assert "/api/auth/browser/v1/auth/signup" in schema["paths"]
    assert "/api/auth/browser/v1/auth/provider/redirect" in schema["paths"]
    assert "/api/health/" in schema["paths"]


def test_the_generated_schema_keeps_the_authentication_schemas(client):
    schema = client.get("/api/schema/?format=json").json()

    assert "Signup" in schema["components"]["schemas"]
    assert "Health" in schema["components"]["schemas"]


def test_a_path_described_twice_stops_the_generation_instead_of_being_overwritten():
    with pytest.raises(ImproperlyConfigured):
        merge_without_overwriting({"/api/health/": {}}, {"/api/health/": {}}, "paths")
