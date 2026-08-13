from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from app.repositories.walking_route import WalkingRouteRepository
from app.schemas.walking_route import WalkingRouteResponse


class WalkingRouteNotFoundError(LookupError):
    """Raised when no pre-computed route exists for the requested pair."""


class WalkingRouteDataError(RuntimeError):
    """Raised when a stored route cannot safely be rendered."""


def route_coordinates_from_value(value: Any) -> list[tuple[float, float]]:
    """Validate DB JSONB coordinates and preserve GeoJSON [longitude, latitude] order."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise WalkingRouteDataError("Stored route coordinates are not valid JSON.") from exc
    if not isinstance(value, list) or len(value) < 2:
        raise WalkingRouteDataError("Stored route must contain at least two coordinates.")

    coordinates: list[tuple[float, float]] = []
    for coordinate in value:
        if not isinstance(coordinate, (list, tuple)) or len(coordinate) != 2:
            raise WalkingRouteDataError("Stored route contains an invalid coordinate.")
        longitude, latitude = float(coordinate[0]), float(coordinate[1])
        if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
            raise WalkingRouteDataError("Stored route contains an out-of-range coordinate.")
        coordinates.append((longitude, latitude))
    return coordinates


class WalkingRouteService:
    """Map-facing access to stored walking routes only."""

    def __init__(self, repository: WalkingRouteRepository | None = None) -> None:
        self.repository = repository or WalkingRouteRepository()

    async def get_walking_route(
        self,
        *,
        complex_id: str,
        feature_id: str,
    ) -> WalkingRouteResponse:
        row = await self.repository.get_latest_route(
            complex_id=complex_id,
            feature_id=feature_id,
            main_origin_id="complex_center",
        )
        if not row:
            # Only pairs under the local 1 km pre-computation policy are loaded.
            raise WalkingRouteNotFoundError(f"No stored walking route for {complex_id}/{feature_id}.")
        return self._response_from_row(row)

    async def get_elementary_school_route(
        self,
        *,
        complex_id: str,
        feature_id: str,
    ) -> WalkingRouteResponse:
        """Compatibility alias for existing callers of the original endpoint."""
        return await self.get_walking_route(complex_id=complex_id, feature_id=feature_id)

    @staticmethod
    def _response_from_row(row: Mapping[str, Any]) -> WalkingRouteResponse:
        required = (
            "complex_id",
            "feature_id",
            "access_group",
            "route_coordinates",
            "walk_distance_m",
            "walk_time_min",
            "route_method",
            "calculated_at",
        )
        missing = [name for name in required if row.get(name) is None]
        if missing:
            raise WalkingRouteDataError(f"Stored route is missing required fields: {', '.join(missing)}")
        return WalkingRouteResponse(
            complex_id=str(row["complex_id"]),
            feature_id=str(row["feature_id"]),
            access_group=str(row["access_group"]),
            route_coordinates=route_coordinates_from_value(row["route_coordinates"]),
            walk_distance_meters=float(row["walk_distance_m"]),
            walk_time_minutes=float(row["walk_time_min"]),
            route_method=str(row["route_method"]),
            calculated_at=row["calculated_at"],
        )
