import pytest

from app.schemas.family_map import ApartmentSummary, FeatureSummary, NearbyFeaturesResponse
from app.services.family_map import FamilyMapService


def apartment(complex_id: str, name: str) -> ApartmentSummary:
    return ApartmentSummary(
        id=complex_id,
        name=name,
        address="서울특별시 양천구",
        latitude=37.52,
        longitude=126.86,
    )


def nearby(complex_id: str, name: str, counts: dict[str, int]) -> NearbyFeaturesResponse:
    return NearbyFeaturesResponse(
        apartment=apartment(complex_id, name),
        radius_m=1000,
        categories=["kids", "school", "crosswalk", "signal", "cctv", "risk"],
        summary=[FeatureSummary(category=category, count=count) for category, count in counts.items()],
        features=[],
    )


@pytest.mark.anyio
async def test_compare_apartments_builds_metric_rows_and_summary(monkeypatch):
    service = FamilyMapService(repository=object())
    responses = {
        "base": nearby("base", "기준단지", {"kids": 10, "school": 2, "crosswalk": 8, "signal": 4, "cctv": 20, "risk": 1}),
        "target": nearby("target", "비교단지", {"kids": 30, "school": 5, "crosswalk": 15, "signal": 7, "cctv": 50, "risk": 0}),
    }

    async def fake_nearby(complex_id: str, *args, **kwargs):
        return responses[complex_id]

    monkeypatch.setattr(service, "get_nearby_features", fake_nearby)

    result = await service.compare_apartments("base", ["target"], 1000)

    assert result.base.name == "기준단지"
    assert result.targets[0].apartment.name == "비교단지"
    assert result.base_metrics["kids"] == 10
    assert result.targets[0].metrics["kids"] == 30
    assert result.metrics[0].targets[0].diff == 20
    assert result.metrics[0].targets[0].label == "돌봄·놀이 선택지 많음"
    assert "비교단지" in result.summary[0]
    assert result.targets[0].insights


@pytest.mark.anyio
async def test_compare_apartments_rejects_base_as_target():
    service = FamilyMapService(repository=object())

    with pytest.raises(ValueError):
        await service.compare_apartments("base", ["base"], 1000)
