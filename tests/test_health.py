def test_health_reports_the_service_as_up(client):
    response = client.get("/api/health/")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_reports_the_version_the_generated_schema_announces(client):
    schema = client.get("/api/schema/?format=json").json()

    response = client.get("/api/health/")

    assert response.json()["version"] == schema["info"]["version"]


def test_health_reports_the_commit_the_image_was_built_from(client, settings):
    settings.GIT_COMMIT = "d6a13f0c1e2b4a5978f30c6d2b1e4a7c9f085b3d"

    response = client.get("/api/health/")

    assert response.json()["commit"] == "d6a13f0c1e2b4a5978f30c6d2b1e4a7c9f085b3d"


def test_health_reports_an_empty_commit_outside_a_released_image(client):
    response = client.get("/api/health/")

    assert response.json()["commit"] == ""


def test_the_generated_docs_are_served_under_the_api_prefix(client):
    response = client.get("/api/docs/")

    assert response.status_code == 200


def test_the_generated_schema_describes_the_health_operation(client):
    schema = client.get("/api/schema/?format=json").json()

    assert schema["paths"]["/api/health/"]["get"]["summary"] == "Health check"
