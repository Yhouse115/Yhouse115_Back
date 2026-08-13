from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_get_building_unit_types_success():
    response = client.get("/buildings/unit-types?pnu=1147010100103140000")
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == 200
    assert res["message"] == "SUCCESS"
    data = res["data"]
    assert "totalBuildings" in data
    assert len(data["items"]) > 0
    bld = data["items"][0]
    assert bld["pnu"] == "1147010100103140000"
    assert len(bld["unitTypes"]) > 0
    u = bld["unitTypes"][0]
    assert "exclusiveArea" in u
    assert "pyungType" in u
    assert "householdCount" in u


def test_get_building_unit_types_missing_params():
    response = client.get("/buildings/unit-types")
    assert response.status_code == 400


def test_get_building_unit_types_not_found():
    response = client.get("/buildings/unit-types?pnu=9999999999999999999")
    assert response.status_code == 404
    res = response.json()
    assert "UNIT_TYPES_NOT_FOUND" in res["detail"]
