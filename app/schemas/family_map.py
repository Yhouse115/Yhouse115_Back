from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ApartmentSummary(BaseModel):
    id: str
    name: str
    address: str
    latitude: float
    longitude: float
    approval_date: Optional[str] = None
    household_count: Optional[int] = None
    building_count: Optional[int] = None


class ApartmentSearchResponse(BaseModel):
    items: List[ApartmentSummary]


class MapFeature(BaseModel):
    id: str
    category: str
    source: str
    name: str
    latitude: float
    longitude: float
    address: Optional[str] = None
    distance_m: Optional[float] = None
    walking_distance_m: Optional[float] = None
    walking_time_min: Optional[float] = None
    geometry: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FeatureSummary(BaseModel):
    category: str
    count: int


class NearbyFeaturesResponse(BaseModel):
    apartment: ApartmentSummary
    radius_m: int
    categories: List[str]
    summary: List[FeatureSummary]
    features: List[MapFeature]


class BoundsFeaturesResponse(BaseModel):
    bounds: Dict[str, float]
    categories: List[str]
    summary: List[FeatureSummary]
    features: List[MapFeature]
