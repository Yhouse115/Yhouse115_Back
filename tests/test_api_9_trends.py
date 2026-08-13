from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_get_dong_trends_summary_404():
    response = client.get("/api/v1/summary/trends?admin_dong_code=0000000000")
    assert response.status_code == 404


def test_get_dong_trends_summary_success():
    # Test with Shinjeong 1-dong (1147062000)
    response = client.get("/api/v1/summary/trends?admin_dong_code=1147062000&period_months=3")
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == 200
    assert res["message"] == "SUCCESS"
    data = res["data"]
    assert data["adminDongCode"] == "1147062000"
    assert "baseDongStats" in data
    assert "unitSizeStats" in data["baseDongStats"]
    assert len(data["baseDongStats"]["unitSizeStats"]) == 3
    assert "adjacentDongs" in data
    assert "adjacentAvgPyeongPrice" in data
    assert "guAvgPyeongPrice" in data
