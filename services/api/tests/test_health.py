from fastapi.testclient import TestClient

from axis_api.main import create_app


def test_health_returns_ok() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "axis-api"}


def test_ready_returns_dependency_configuration_without_secrets() -> None:
    client = TestClient(create_app())
    response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["dependencies"] == {
        "postgres": True,
        "typedb": True,
        "temporal": True,
    }
    assert "password" not in str(body).lower()


def test_local_console_origin_is_allowed_for_cors_preflight() -> None:
    client = TestClient(create_app())
    response = client.options(
        "/ready",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_openapi_metadata_names_axis() -> None:
    client = TestClient(create_app())
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Limes Axis API"
    assert "/ready" in response.json()["paths"]
