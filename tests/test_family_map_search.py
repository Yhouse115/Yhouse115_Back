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


@pytest.mark.anyio
async def test_search_apartments_keeps_large_unfiltered_limit() -> None:
    repository = FakeFamilyMapRepository()
    service = FamilyMapService(repository=repository)

    apartments = await service.search_apartments(None, 507)

    assert repository.requested_limit == 507
    assert len(apartments) == 507
