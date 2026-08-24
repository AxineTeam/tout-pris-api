from importlib.metadata import version

from django.test import override_settings


@override_settings(GIT_COMMIT="")
def test_health_reports_the_service_as_up_with_the_version_it_runs(client):
    response = client.get("/api/health/")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": version("tout-pris-back"),
        "commit": "",
    }


@override_settings(GIT_COMMIT="d6a13f0c1e2b4a5978f30c6d2b1e4a7c9f085b3d")
def test_health_reports_the_commit_the_image_was_built_from(client):
    response = client.get("/api/health/")

    assert response.json()["commit"] == "d6a13f0c1e2b4a5978f30c6d2b1e4a7c9f085b3d"


def test_the_generated_docs_are_served_under_the_api_prefix(client):
    response = client.get("/api/docs/")

    assert response.status_code == 200


def test_the_generated_schema_describes_the_health_operation(client):
    schema = client.get("/api/schema/?format=json").json()

    assert schema["paths"]["/api/health/"]["get"]["summary"] == "Health check"
