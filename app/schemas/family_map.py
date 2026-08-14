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


class ApartmentCompareRequest(BaseModel):
    base_apartment_id: str
    target_apartment_ids: List[str] = Field(min_length=1, max_length=2)
    radius_m: int = Field(default=1000, ge=1, le=3000)


class ApartmentCompareMetricTarget(BaseModel):
    apartment_id: str
    count: int
    diff: int
    comparison: str
    label: str
    tone: str


class ApartmentCompareMetric(BaseModel):
    code: str
    label: str
    unit: str
    base_count: int
    targets: List[ApartmentCompareMetricTarget]


class ApartmentCompareInsight(BaseModel):
    category: str
    title: str
    description: str
    tone: str
    metric_codes: List[str] = Field(default_factory=list)


class ApartmentCompareTarget(BaseModel):
    apartment: ApartmentSummary
    metrics: Dict[str, int]
    summary: str
    insights: List[ApartmentCompareInsight]


class ApartmentCompareResponse(BaseModel):
    base: ApartmentSummary
    radius_m: int
    categories: List[str]
    base_metrics: Dict[str, int]
    targets: List[ApartmentCompareTarget]
    metrics: List[ApartmentCompareMetric]
    summary: List[str]
