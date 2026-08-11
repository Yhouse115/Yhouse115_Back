from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_root_health_check() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "WhyHouse Backend"


def test_versioned_health_check() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_runtime_config_check() -> None:
    response = client.get("/api/v1/system/config")

    assert response.status_code == 200
    body = response.json()
    assert body["environment"] == "local"
    assert body["api_prefix"] == "/api/v1"
    assert "dependencies" in body


def test_dependency_status_check() -> None:
    response = client.get("/api/v1/system/dependencies")

    assert response.status_code == 200
    body = response.json()
    assert "database_configured" in body
    assert "supabase_configured" in body
    assert "naver_maps_configured" in body
