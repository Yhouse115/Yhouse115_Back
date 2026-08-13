from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings


class WalkingRouteRepository:
    """Read pre-computed route geometries from the Supabase serving table."""

    def __init__(self) -> None:
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for the walking route API.")
        self.base_url = settings.supabase_url.rstrip("/") + "/rest/v1/"
        self.headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
        }

    async def _get(self, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(self.base_url + table, params=params, headers=self.headers)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Walking route table query failed: {table}") from exc
        payload = response.json()
        if not isinstance(payload, list):
            raise RuntimeError(f"Unexpected walking route table response: {table}")
        return [dict(row) for row in payload]

    async def get_latest_route(
        self,
        *,
        complex_id: str,
        feature_id: str,
        main_origin_id: str = "complex_center",
    ) -> dict[str, Any] | None:
        """Return the newest stored route; do not perform a network calculation."""
        rows = await self._get(
            "complex_feature_walking_route",
            {
                "select": (
                    "complex_id,feature_id,access_group,main_origin_id,calculation_version,"
                    "route_coordinates,walk_distance_m,walk_time_min,route_method,calculated_at,"
                    "safety_match_threshold_m,crosswalk_count,pedestrian_signal_count,"
                    "cctv_location_count,safety_calculation_version,safety_calculated_at"
                ),
                "complex_id": f"eq.{complex_id}",
                "feature_id": f"eq.{feature_id}",
                "main_origin_id": f"eq.{main_origin_id}",
                "order": "calculated_at.desc,calculation_version.desc",
                "limit": "1",
            },
        )
        return rows[0] if rows else None

    async def get_latest_route_summaries(
        self,
        *,
        complex_id: str,
        feature_ids: list[str],
        main_origin_id: str = "complex_center",
    ) -> dict[str, dict[str, Any]]:
        """Return one newest distance/time summary for each requested facility."""
        if not feature_ids:
            return {}
        feature_filter = "in.(" + ",".join(feature_ids) + ")"
        rows = await self._get(
            "complex_feature_walking_route",
            {
                "select": "feature_id,walk_distance_m,walk_time_min,calculated_at,calculation_version",
                "complex_id": f"eq.{complex_id}",
                "feature_id": feature_filter,
                "main_origin_id": f"eq.{main_origin_id}",
                "order": "feature_id,calculated_at.desc,calculation_version.desc",
            },
        )
        latest: dict[str, dict[str, Any]] = {}
        for row in rows:
            feature_id = str(row.get("feature_id") or "")
            if feature_id and feature_id not in latest:
                latest[feature_id] = row
        return latest

    async def get_latest_access_summaries(
        self,
        *,
        complex_id: str,
        access_group: str,
        main_origin_id: str = "complex_center",
    ) -> dict[str, dict[str, Any]]:
        """Return compact walking facts when a route geometry is intentionally absent."""
        rows = await self._get(
            "complex_feature_access",
            {
                "select": "feature_id,walk_distance_m,walk_time_min,reference_date,loaded_at,calculation_version",
                "complex_id": f"eq.{complex_id}",
                "access_group": f"eq.{access_group}",
                "main_origin_id": f"eq.{main_origin_id}",
                "access_status": "eq.available",
                "order": "feature_id,reference_date.desc.nullslast,loaded_at.desc,calculation_version.desc",
            },
        )
        latest: dict[str, dict[str, Any]] = {}
        for row in rows:
            feature_id = str(row.get("feature_id") or "")
            if feature_id and feature_id not in latest:
                latest[feature_id] = row
        return latest
