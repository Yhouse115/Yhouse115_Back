from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_get_development_detail_404():
    response = client.get("/api/v1/developments/DEV_INVALID_PROJECT_ID_99999")
    assert response.status_code == 404


def test_get_development_detail_success():
    # 1. Fetch list of developments to get a valid project_id or PNU
    list_res = client.get("/api/v1/developments?size=1")
    assert list_res.status_code == 200
    items = list_res.json()["data"]["items"]
    assert len(items) > 0
    proj_id = items[0]["projectId"]

    # 2. Query development detail API
    detail_res = client.get(f"/api/v1/developments/{proj_id}")
    assert detail_res.status_code == 200
    res = detail_res.json()
    assert res["status"] == 200
    assert res["message"] == "SUCCESS"
    data = res["data"]
    assert data["projectId"] == proj_id
    assert "projectName" in data
    assert "currentStage" in data
    assert "history" in data
    assert len(data["history"]) > 0
