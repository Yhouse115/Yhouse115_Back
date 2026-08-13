from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import httpx

from app.core.config import settings

CacheKey = Tuple[str, Tuple[Tuple[str, Any], ...]]
_CACHE_TTL_SECONDS = 20
_response_cache: Dict[CacheKey, Tuple[float, List[Dict[str, Any]]]] = {}


def _normalize_params(params: Union[Dict[str, Any], Sequence[Tuple[str, Any]]]) -> Tuple[Tuple[str, Any], ...]:
    if isinstance(params, dict):
        return tuple(sorted(params.items()))
    return tuple(params)


class FamilyMapRepository:
    def __init__(self) -> None:
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required.")

        self.base_url = settings.supabase_url.rstrip("/")
        self.headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
        }
        self.client = httpx.AsyncClient(base_url=self.base_url, headers=self.headers, timeout=10.0)

    async def _get(
        self,
        table: str,
        params: Union[Dict[str, Any], Sequence[Tuple[str, Any]]],
    ) -> List[Dict[str, Any]]:
        cache_key = (table, _normalize_params(params))
        cached = _response_cache.get(cache_key)
        if cached and cached[0] > time.monotonic():
            return cached[1]

        response = await self.client.get(f"/rest/v1/{table}", params=params)
        response.raise_for_status()
        data = response.json()
        _response_cache[cache_key] = (time.monotonic() + _CACHE_TTL_SECONDS, data)
        return data

    async def search_apartments(self, query: Optional[str], limit: int) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {
            "select": ",".join(
                [
                    "complex_id",
                    "name",
                    "road_address",
                    "parcel_address",
                    "approval_date",
                    "household_count",
                    "building_count",
                    "latitude",
                    "longitude",
                ]
            ),
            "latitude": "not.is.null",
            "longitude": "not.is.null",
            "order": "household_count.desc.nullslast,name,complex_id",
            "limit": str(limit),
        }

        if query:
            escaped = query.replace("*", "").replace(",", " ")
            params["or"] = (
                f"(name.ilike.*{escaped}*,"
                f"road_address.ilike.*{escaped}*,"
                f"parcel_address.ilike.*{escaped}*)"
            )

        return await self._get("apartment_complex", params)

    async def get_apartment(self, complex_id: str) -> Optional[Dict[str, Any]]:
        rows = await self._get(
            "apartment_complex",
            {
                "select": ",".join(
                    [
                        "complex_id",
                        "name",
                        "road_address",
                        "parcel_address",
                        "approval_date",
                        "household_count",
                        "building_count",
                        "latitude",
                        "longitude",
                    ]
                ),
                "complex_id": f"eq.{complex_id}",
                "limit": "1",
            },
        )
        return rows[0] if rows else None

    async def fetch_bbox(
        self,
        table: str,
        select: str,
        lat_column: str,
        lng_column: str,
        sw_lat: float,
        sw_lng: float,
        ne_lat: float,
        ne_lng: float,
        limit: int,
        filters: Sequence[Tuple[str, str]] = (),
    ) -> List[Dict[str, Any]]:
        params: List[Tuple[str, Any]] = [
            ("select", select),
            (lat_column, f"gte.{sw_lat}"),
            (lat_column, f"lte.{ne_lat}"),
            (lng_column, f"gte.{sw_lng}"),
            (lng_column, f"lte.{ne_lng}"),
            *filters,
            ("limit", str(limit)),
        ]
        return await self._get(table, params)
