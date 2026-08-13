from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_get_rents_list():
    response = client.get(
        "/transactions/rents?admin_dong_code=1147051000&period_start=2020-01-01&period_end=2026-08-12&page=1&size=10"
    )
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == 200
    assert res["message"] == "SUCCESS"
    data = res["data"]
    assert "pagination" in data
    assert "items" in data
    assert data["pagination"]["page"] == 1
    assert data["pagination"]["size"] == 10
    if len(data["items"]) > 0:
        item = data["items"][0]
        assert item["rentId"].startswith("RN_")
        assert "pnu" in item
        assert "deposit" in item
        assert "monthlyRent" in item
        assert item["rentType"] in ["JEONSE", "MONTHLY"]


def test_get_rents_list_with_filters():
    response = client.get(
        "/api/v1/transactions/rents?period_start=2020-01-01&period_end=2026-08-12&rent_type=JEONSE&building_type=APT&min_deposit=40000&page=1&size=5"
    )
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == 200
    data = res["data"]
    assert data["pagination"]["size"] == 5
    for item in data["items"]:
        assert item["rentType"] == "JEONSE"
        assert item["buildingType"] == "APT"
        assert item["deposit"] >= 40000
