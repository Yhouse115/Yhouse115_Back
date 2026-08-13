from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_get_buildings_list():
    response = client.get("/buildings?admin_dong_code=1147051000&page=1&size=10")
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == 200
    assert res["message"] == "SUCCESS"
    data = res["data"]
    assert "pagination" in data
    assert "items" in data
    assert data["pagination"]["page"] == 1
    if len(data["items"]) > 0:
        item = data["items"][0]
        assert "pnu" in item
        assert "buildingType" in item


def test_get_buildings_list_with_name_filter():
    response = client.get("/api/v1/buildings?building_name=신시가지&page=1&size=5")
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == 200
    data = res["data"]
    assert data["pagination"]["size"] == 5
