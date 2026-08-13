from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.environment import ApiModel


class WalkingRoutePedestrianSignal(ApiModel):
    id: str
    longitude: float
    latitude: float


class WalkingRouteCrossingEvent(ApiModel):
    """One crosswalk link genuinely traversed by a stored walking route."""

    crosswalk_link_id: str = Field(serialization_alias="crosswalkLinkId")
    longitude: float
    latitude: float
    pedestrian_signals: list[WalkingRoutePedestrianSignal] = Field(serialization_alias="pedestrianSignals")


class WalkingRouteResponse(ApiModel):
    """A pre-computed, render-ready route between one complex and one feature."""

    complex_id: str = Field(serialization_alias="complexId")
    feature_id: str = Field(serialization_alias="featureId")
    access_group: str = Field(serialization_alias="accessGroup")
    route_coordinates: list[tuple[float, float]] = Field(serialization_alias="routeCoordinates")
    walk_distance_meters: float = Field(serialization_alias="walkDistanceMeters")
    walk_time_minutes: float = Field(serialization_alias="walkTimeMinutes")
    route_method: str = Field(serialization_alias="routeMethod")
    calculated_at: datetime = Field(serialization_alias="calculatedAt")
    safety_match_threshold_meters: int | None = Field(default=None, serialization_alias="safetyMatchThresholdMeters")
    crosswalk_count: int | None = Field(default=None, serialization_alias="crosswalkCount")
    pedestrian_signal_count: int | None = Field(default=None, serialization_alias="pedestrianSignalCount")
    cctv_location_count: int | None = Field(default=None, serialization_alias="cctvLocationCount")
    crossing_events: list[WalkingRouteCrossingEvent] | None = Field(default=None, serialization_alias="crossingEvents")
