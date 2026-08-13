from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_get_trades_list():
    response = client.get(
        "/transactions/trades?admin_dong_code=1147051000&period_start=2020-01-01&period_end=2026-08-12&page=1&size=10"
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
        assert item["tradeId"].startswith("TR_")
        assert "pnu" in item
        assert "dealAmount" in item
        assert "buildingType" in item


def test_get_trades_list_with_filters():
    response = client.get(
        "/api/v1/transactions/trades?period_start=2020-01-01&period_end=2026-08-12&building_type=APT&apt_name=목동&min_deal_amount=50000&page=1&size=5"
    )
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == 200
    data = res["data"]
    assert data["pagination"]["size"] == 5
    for item in data["items"]:
        assert item["buildingType"] == "APT"
        assert item["dealAmount"] >= 50000
