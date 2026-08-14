from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_get_building_detail_summary_404():
    response = client.get("/api/v1/buildings/0000000000000000000/summary")
    assert response.status_code == 404


def test_get_building_detail_summary_existing():
    # First get a valid PNU from buildings list
    b_res = client.get("/api/v1/buildings?page=1&size=1")
    assert b_res.status_code == 200
    b_data = b_res.json()["data"]
    if len(b_data["items"]) > 0:
        pnu = b_data["items"][0]["pnu"]
        response = client.get(f"/api/v1/buildings/{pnu}/summary")
        assert response.status_code == 200
        res = response.json()
        assert res["status"] == 200
        assert res["message"] == "SUCCESS"
        data = res["data"]
        assert "buildingInfo" in data
        assert data["buildingInfo"]["pnu"] == pnu
        assert "unitTypes" in data
        assert "recentTrades" in data
        assert "priceTrends" in data
