from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.environment import ApiModel


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
