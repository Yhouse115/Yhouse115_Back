from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EnvironmentAxis(str, Enum):
    TRANSPORT = "transport"
    PARKS_PLAY = "parks_play"
    MEDICAL = "medical"
    EDUCATION_CARE = "education_care"
    CONVENIENCE = "convenience"


class AxisStatus(str, Enum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    COMING_SOON = "coming_soon"


class AccessStatus(str, Enum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    NOT_CALCULATED = "not_calculated"


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class ApiMeta(ApiModel):
    request_id: UUID = Field(serialization_alias="requestId")
    schema_version: str = Field(serialization_alias="schemaVersion")
    generated_at: datetime = Field(serialization_alias="generatedAt")
    calculation_version: Optional[str] = Field(default=None, serialization_alias="calculationVersion")
    policy_version: Optional[str] = Field(default=None, serialization_alias="policyVersion")


class Position(ApiModel):
    latitude: float
    longitude: float


class AdminDong(ApiModel):
    code: Optional[str] = None
    name: Optional[str] = None


class ComplexMarker(ApiModel):
    apartment_complex_id: str = Field(serialization_alias="apartmentComplexId")
    name: str
    admin_dong: AdminDong = Field(serialization_alias="adminDong")
    position: Position
    household_count: Optional[int] = Field(default=None, serialization_alias="householdCount")
    approval_date: Optional[str] = Field(default=None, serialization_alias="approvalDate")


class ComplexListResponse(ApiModel):
    meta: ApiMeta
    items: list[ComplexMarker]
    truncated: bool = False


class SourceReference(ApiModel):
    dataset_id: str = Field(serialization_alias="datasetId")
    source_name: str = Field(serialization_alias="sourceName")
    reference_date: Optional[str] = Field(default=None, serialization_alias="referenceDate")


class NearestFeature(ApiModel):
    feature_id: str = Field(serialization_alias="featureId")
    feature_type: str = Field(serialization_alias="featureType")
    name: Optional[str] = None
    walk_distance_meters: Optional[float] = Field(default=None, serialization_alias="walkDistanceMeters")
    walk_time_minutes: Optional[float] = Field(default=None, serialization_alias="walkTimeMinutes")


class AxisSummary(ApiModel):
    axis: EnvironmentAxis
    label: str
    status: AxisStatus
    headline: Optional[str] = None
    nearest: Optional[NearestFeature] = None
    nearest_by_group: dict[str, Optional[NearestFeature]] = Field(
        default_factory=dict,
        serialization_alias="nearestByGroup",
    )
    metrics: dict[str, Any] = Field(default_factory=dict)
    empty_reason: Optional[str] = Field(default=None, serialization_alias="emptyReason")
    failure_reason: Optional[str] = Field(default=None, serialization_alias="failureReason")
    qa_flags: list[str] = Field(default_factory=list, serialization_alias="qaFlags")
    sources: list[SourceReference] = Field(default_factory=list)


class ComplexEnvironmentResponse(ApiModel):
    meta: ApiMeta
    apartment_complex_id: str = Field(serialization_alias="apartmentComplexId")
    summary: list[AxisSummary]


class EnvironmentFeature(ApiModel):
    feature_id: str = Field(serialization_alias="featureId")
    axis: EnvironmentAxis
    feature_type: str = Field(serialization_alias="featureType")
    name: Optional[str] = None
    address: Optional[str] = None
    position: Position
    walk_distance_meters: Optional[float] = Field(default=None, serialization_alias="walkDistanceMeters")
    walk_time_minutes: Optional[float] = Field(default=None, serialization_alias="walkTimeMinutes")
    distance_method: str = Field(serialization_alias="distanceMethod")
    access_status: AccessStatus = Field(serialization_alias="accessStatus")
    source: SourceReference
    attributes: dict[str, Any] = Field(default_factory=dict)
    qa_flags: list[str] = Field(default_factory=list, serialization_alias="qaFlags")


class EnvironmentFeaturesResponse(ApiModel):
    meta: ApiMeta
    apartment_complex_id: str = Field(serialization_alias="apartmentComplexId")
    axis: EnvironmentAxis
    status: AxisStatus
    total_count: int = Field(serialization_alias="totalCount")
    items: list[EnvironmentFeature]


class ApiErrorDetail(ApiModel):
    field: Optional[str] = None
    reason: str


class ApiErrorResponse(ApiModel):
    request_id: UUID = Field(serialization_alias="requestId")
    code: str
    message: str
    details: list[ApiErrorDetail] = Field(default_factory=list)
