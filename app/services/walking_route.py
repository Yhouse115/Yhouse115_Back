from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from app.repositories.walking_route import WalkingRouteRepository
from app.schemas.walking_route import (
    WalkingRouteCrossingEvent,
    WalkingRoutePedestrianSignal,
    WalkingRouteResponse,
)


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


def crossing_events_from_value(value: Any) -> list[WalkingRouteCrossingEvent] | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise WalkingRouteDataError("Stored crossing events are not valid JSON.") from exc
    if not isinstance(value, list):
        raise WalkingRouteDataError("Stored crossing events must be an array.")
    events: list[WalkingRouteCrossingEvent] = []
    seen_link_ids: set[str] = set()
    seen_signal_ids: set[str] = set()
    for event in value:
        if not isinstance(event, Mapping):
            raise WalkingRouteDataError("Stored crossing event must be an object.")
        try:
            link_id = str(event["crosswalk_link_id"]).strip()
            longitude = float(event["longitude"])
            latitude = float(event["latitude"])
            signals_value = event.get("pedestrian_signals", [])
        except (KeyError, TypeError, ValueError) as exc:
            raise WalkingRouteDataError("Stored crossing event is invalid.") from exc
        if not isinstance(signals_value, list):
            raise WalkingRouteDataError("Stored crossing-event signals must be an array.")
        signals: list[WalkingRoutePedestrianSignal] = []
        signal_ids: list[str] = []
        for signal in signals_value:
            if not isinstance(signal, Mapping):
                raise WalkingRouteDataError("Stored crossing-event signal must be an object.")
            try:
                signal_id = str(signal["id"]).strip()
                signal_longitude = float(signal["longitude"])
                signal_latitude = float(signal["latitude"])
            except (KeyError, TypeError, ValueError) as exc:
                raise WalkingRouteDataError("Stored crossing-event signal is invalid.") from exc
            if not signal_id or not -180 <= signal_longitude <= 180 or not -90 <= signal_latitude <= 90:
                raise WalkingRouteDataError("Stored crossing-event signal is invalid.")
            signal_ids.append(signal_id)
            signals.append(WalkingRoutePedestrianSignal(id=signal_id, longitude=signal_longitude, latitude=signal_latitude))
        if (
            not link_id
            or link_id in seen_link_ids
            or not -180 <= longitude <= 180
            or not -90 <= latitude <= 90
            or any(not signal_id for signal_id in signal_ids)
            or len(signal_ids) != len(set(signal_ids))
            or seen_signal_ids.intersection(signal_ids)
        ):
            raise WalkingRouteDataError("Stored crossing event is invalid or duplicated.")
        seen_link_ids.add(link_id)
        seen_signal_ids.update(signal_ids)
        events.append(WalkingRouteCrossingEvent(
            crosswalk_link_id=link_id,
            longitude=longitude,
            latitude=latitude,
            pedestrian_signals=signals,
        ))
    return events


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
        crossing_events = crossing_events_from_value(row.get("route_crossing_events"))
        crosswalk_count = optional_count(row.get("crosswalk_count"))
        pedestrian_signal_count = optional_count(row.get("pedestrian_signal_count"))
        if crossing_events is not None and (
            crosswalk_count != len(crossing_events)
            or pedestrian_signal_count != sum(len(event.pedestrian_signals) for event in crossing_events)
        ):
            raise WalkingRouteDataError("Stored crossing-event counts do not match the crossing events.")
        return WalkingRouteResponse(
            complex_id=str(row["complex_id"]),
            feature_id=str(row["feature_id"]),
            access_group=str(row["access_group"]),
            route_coordinates=route_coordinates_from_value(row["route_coordinates"]),
            walk_distance_meters=float(row["walk_distance_m"]),
            walk_time_minutes=float(row["walk_time_min"]),
            route_method=str(row["route_method"]),
            calculated_at=row["calculated_at"],
            safety_match_threshold_meters=optional_count(row.get("safety_match_threshold_m")),
            crosswalk_count=crosswalk_count,
            pedestrian_signal_count=pedestrian_signal_count,
            cctv_location_count=optional_count(row.get("cctv_location_count")),
            crossing_events=crossing_events,
        )


def optional_count(value: Any) -> int | None:
    if value is None:
        return None
    parsed = int(value)
    if parsed < 0:
        raise WalkingRouteDataError("Stored route has a negative safety count.")
    return parsed
