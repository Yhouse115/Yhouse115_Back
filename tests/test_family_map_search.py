from __future__ import annotations

import pytest

from app.services.family_map import FamilyMapService


class FakeFamilyMapRepository:
    def __init__(self) -> None:
        self.requested_limit: int | None = None

    async def search_apartments(self, query: str | None, limit: int) -> list[dict[str, object]]:
        self.requested_limit = limit
        return [
            {
                "complex_id": f"APT-{index}",
                "complex_name_official_price": f"Apartment {index}",
                "complex_name_building_register": None,
                "complex_name_road_address": None,
                "address": f"Road {index}",
                "approval_date": None,
                "household_count": 100 + index,
                "building_count": 1,
                "latitude": 37.5,
                "longitude": 126.8,
            }
            for index in range(limit)
        ]


class FakeWalkingRouteRepository:
    async def get_latest_route_summaries(
        self,
        *,
        complex_id: str,
        feature_ids: list[str],
        main_origin_id: str = "complex_center",
    ) -> dict[str, dict[str, object]]:
        assert complex_id == "APT-1"
        assert feature_ids == ["education_elementary_yangcheon:7081453"]
        assert main_origin_id == "complex_center"
        return {
            "education_elementary_yangcheon:7081453": {
                "walk_distance_m": 982.4,
                "walk_time_min": 13.7,
            }
        }


class FakeCompactMedicalAccessRepository:
    async def get_latest_route_summaries(
        self,
        **_: object,
    ) -> dict[str, dict[str, object]]:
        return {}

    async def get_latest_access_summaries(
        self,
        *,
        complex_id: str,
        access_group: str,
        main_origin_id: str = "complex_center",
    ) -> dict[str, dict[str, object]]:
        assert complex_id == "APT-1"
        assert access_group == "medical_clinic"
        assert main_origin_id == "complex_center"
        return {
            "healthcare_hospitals_seoul:A1103009": {
                "walk_distance_m": 270.8,
                "walk_time_min": 3.87,
            }
        }


@pytest.mark.anyio
async def test_search_apartments_keeps_large_unfiltered_limit() -> None:
    repository = FakeFamilyMapRepository()
    service = FamilyMapService(repository=repository)

    apartments = await service.search_apartments(None, 507)

    assert repository.requested_limit == 507
    assert len(apartments) == 507


@pytest.mark.anyio
async def test_attaches_stored_walking_summary_to_route_eligible_feature() -> None:
    service = FamilyMapService(
        repository=FakeFamilyMapRepository(),
        walking_route_repository=FakeWalkingRouteRepository(),
    )
    from app.schemas.family_map import MapFeature

    features = [
        MapFeature(
            id="elementary_schools:7081453",
            category="school",
            source="elementary_schools",
            name="서울월촌초등학교",
            latitude=37.54,
            longitude=126.87,
        )
    ]

    await service._attach_stored_walking_summaries("APT-1", features)

    assert features[0].walking_distance_m == 982.4
    assert features[0].walking_time_min == 13.7


@pytest.mark.anyio
async def test_keeps_hospital_walking_summary_from_compact_access_rows_without_geometry() -> None:
    from app.schemas.family_map import MapFeature

    service = FamilyMapService(
        repository=FakeFamilyMapRepository(),
        walking_route_repository=FakeCompactMedicalAccessRepository(),
    )
    features = [
        MapFeature(
            id="healthcare_hospitals_seoul:A1103009",
            category="hospital",
            source="environment_medical",
            name="Hospital",
            latitude=37.54,
            longitude=126.87,
        )
    ]

    await service._attach_stored_walking_summaries("APT-1", features)

    assert features[0].walking_distance_m == 270.8
    assert features[0].walking_time_min == 3.87
