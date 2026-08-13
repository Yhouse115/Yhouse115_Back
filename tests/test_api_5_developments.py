from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_get_developments_list():
    response = client.get("/developments?page=1&size=10")
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == 200
    assert res["message"] == "SUCCESS"
    data = res["data"]
    assert "pagination" in data
    assert "items" in data
    assert data["pagination"]["page"] == 1
    if len(data["items"]) > 0:
        dev = data["items"][0]
        assert dev["projectId"].startswith("DEV_")
        assert "projectName" in dev
        assert "history" in dev
        assert isinstance(dev["history"], list)
        if dev["currentStage"]:
            assert "stageCode" in dev["currentStage"]
            assert "stageName" in dev["currentStage"]


def test_get_developments_list_with_prefix_and_filters():
    response = client.get("/api/v1/developments?admin_dong_code=1147064000&dev_type=REDEVELOPMENT&page=1&size=5")
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == 200
    data = res["data"]
    assert data["pagination"]["size"] == 5
    for item in data["items"]:
        assert item["devType"] == "재개발"
        assert item["adminDongCode"] == "1147064000"
