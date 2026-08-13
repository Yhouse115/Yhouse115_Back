from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_get_summary_transaction_count():
    response = client.get(
        "/summary/transaction-count?admin_dong_code=1147051000&period_start=2026-05-14&period_end=2026-08-12"
    )
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == 200
    assert res["message"] == "SUCCESS"
    data = res["data"]
    assert data["adminDongCode"] == "1147051000"
    assert data["periodStart"] == "2026-05-14"
    assert data["periodEnd"] == "2026-08-12"
    assert "series" in data
    assert isinstance(data["series"], list)
    if len(data["series"]) > 0:
        s0 = data["series"][0]
        assert "yearMonth" in s0
        assert "totalCount" in s0
        assert "counts" in s0


def test_get_summary_transaction_count_prefix():
    response = client.get(
        "/api/v1/summary/transaction-count?admin_dong_code=1147051000&period_start=2026-05-14&period_end=2026-08-12&transaction_type=TRADE&building_type=APT"
    )
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == 200
    data = res["data"]
    assert data["transactionTypes"] == ["TRADE"]
    assert data["buildingTypes"] == ["APT"]
