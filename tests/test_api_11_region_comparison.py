from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_get_region_comparison_404():
    response = client.get("/api/v1/summary/region-comparison?base_admin_dong_code=0000000000&target_admin_dong_code=1147062000")
    assert response.status_code == 404


def test_get_region_comparison_success():
    # Compare Mok 1-dong (1147051000) vs Shinjeong 1-dong (1147062000)
    response = client.get("/api/v1/summary/region-comparison?base_admin_dong_code=1147051000&target_admin_dong_code=1147062000&period_months=3")
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == 200
    assert res["message"] == "SUCCESS"
    data = res["data"]
    assert data["baseRegion"]["adminDongCode"] == "1147051000"
    assert data["targetRegion"]["adminDongCode"] == "1147062000"
    assert "comparisonSummary" in data
    assert "higherPyeongPriceRegion" in data["comparisonSummary"]
