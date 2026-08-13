from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_get_summary_inventory():
    response = client.get("/summary/inventory?admin_dong_code=1147051000")
    assert response.status_code == 200
    data = response.json()
    assert data["admin_dong_code"] == "1147051000"
    assert "admin_dong_name" in data
    assert "total_stock_count" in data
    assert "items" in data
    assert len(data["items"]) == 3
    
    house_types = [item["house_type"] for item in data["items"]]
    assert "APT" in house_types
    assert "TOWNHOUSE" in house_types
    assert "OFFICETEL" in house_types


def test_get_summary_inventory_prefix():
    response = client.get("/api/v1/summary/inventory?admin_dong_code=1147051000")
    assert response.status_code == 200
    data = response.json()
    assert data["admin_dong_code"] == "1147051000"
    assert len(data["items"]) == 3
