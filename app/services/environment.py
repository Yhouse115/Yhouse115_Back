from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.repositories.environment import EnvironmentRepository
from app.schemas.environment import (
    AccessStatus,
    AdminDong,
    ApiMeta,
    AxisStatus,
    AxisSummary,
    ComplexEnvironmentResponse,
    ComplexListResponse,
    ComplexMarker,
    EnvironmentAxis,
    EnvironmentFeature,
    EnvironmentFeaturesResponse,
    NearestFeature,
    Position,
    SourceReference,
)

SCHEMA_VERSION = "1.0.0"


class EnvironmentNotFoundError(LookupError):
    """Raised when an API request refers to an unknown apartment complex."""


@dataclass(frozen=True)
class AxisDefinition:
    axis: EnvironmentAxis
    label: str
    access_groups: tuple[str, ...]
    preferred_nearest_group: str | None


AXIS_DEFINITIONS: tuple[AxisDefinition, ...] = (
    AxisDefinition(
        axis=EnvironmentAxis.TRANSPORT,
        label="교통",
        access_groups=("subway_exit", "bus_stop"),
        preferred_nearest_group="subway_exit",
    ),
    AxisDefinition(
        axis=EnvironmentAxis.PARKS_PLAY,
        label="공원·놀이",
        access_groups=("park", "playground"),
        preferred_nearest_group="park",
    ),
    AxisDefinition(
        axis=EnvironmentAxis.MEDICAL,
        label="의료·약국",
        access_groups=("pediatrics", "obstetrics_gynecology", "pharmacy"),
        preferred_nearest_group="pediatrics",
    ),
    AxisDefinition(
        axis=EnvironmentAxis.EDUCATION_CARE,
        label="교육·돌봄",
        access_groups=("childcare", "kindergarten", "elementary_school"),
        preferred_nearest_group="elementary_school",
    ),
    AxisDefinition(
        axis=EnvironmentAxis.CONVENIENCE,
        label="생활편의",
        access_groups=("daily_convenience",),
        preferred_nearest_group="daily_convenience",
    ),
)
AXIS_BY_KEY = {definition.axis: definition for definition in AXIS_DEFINITIONS}


def as_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    if isinstance(value, str):
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    return {}


def as_flags(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, tuple):
        return [str(item) for item in value if item]
    if isinstance(value, str):
        return [item.strip() for item in value.split("|") if item.strip()]
    return []


def optional_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def optional_int(value: Any) -> int | None:
    return int(value) if value is not None else None


def display_minutes(value: float | None) -> int | None:
    return math.ceil(value) if value is not None else None


def display_distance(value: float | None) -> int | None:
    return round(value) if value is not None else None


def source_from_row(row: Mapping[str, Any], *, prefix: str = "") -> SourceReference | None:
    dataset_id = row.get(f"{prefix}source_dataset_id")
    source_name = row.get(f"{prefix}source_name")
    if not dataset_id or not source_name:
        return None
    return SourceReference(
        dataset_id=str(dataset_id),
        source_name=str(source_name),
        reference_date=(
            str(row[f"{prefix}source_reference_date"])
            if row.get(f"{prefix}source_reference_date") is not None
            else None
        ),
    )


def nearest_from_summary_row(row: Mapping[str, Any]) -> NearestFeature | None:
    feature_id = row.get("nearest_feature_id")
    feature_type = row.get("nearest_feature_type")
    if not feature_id or not feature_type:
        return None
    return NearestFeature(
        feature_id=str(feature_id),
        feature_type=str(feature_type),
        name=str(row["nearest_feature_name"]) if row.get("nearest_feature_name") else None,
        walk_distance_meters=optional_float(row.get("nearest_walk_distance_m")),
        walk_time_minutes=optional_float(row.get("nearest_walk_time_min")),
    )


class EnvironmentService:
    def __init__(self, repository: EnvironmentRepository | None = None) -> None:
        self.repository = repository or EnvironmentRepository()

    @staticmethod
    def _meta(summary_rows: Iterable[Mapping[str, Any]] = ()) -> ApiMeta:
        first = next(iter(summary_rows), None)
        return ApiMeta(
            request_id=uuid4(),
            schema_version=SCHEMA_VERSION,
            generated_at=datetime.now(UTC),
            calculation_version=str(first["calculation_version"]) if first and first.get("calculation_version") else None,
            policy_version=str(first["policy_version"]) if first and first.get("policy_version") else None,
        )

    async def list_complexes(self, district: str, limit: int) -> ComplexListResponse:
        rows = await self.repository.list_complexes(district, limit)
        return ComplexListResponse(
            meta=self._meta(),
            items=[
                ComplexMarker(
                    apartment_complex_id=str(row["complex_id"]),
                    name=str(row["name"]),
                    admin_dong=AdminDong(
                        code=str(row["admin_dong_code"]) if row.get("admin_dong_code") else None,
                        name=str(row["admin_dong_name"]) if row.get("admin_dong_name") else None,
                    ),
                    position=Position(latitude=float(row["latitude"]), longitude=float(row["longitude"])),
                    household_count=optional_int(row.get("household_count")),
                    approval_date=str(row["approval_date"]) if row.get("approval_date") else None,
                )
                for row in rows
            ],
            truncated=len(rows) == limit,
        )

    async def get_environment(self, complex_id: str) -> ComplexEnvironmentResponse:
        await self._require_complex(complex_id)
        summary_rows = await self.repository.get_summaries(complex_id)
        return ComplexEnvironmentResponse(
            meta=self._meta(summary_rows),
            apartment_complex_id=complex_id,
            summary=self._build_axis_summaries(summary_rows),
        )

    async def get_axis_features(
        self,
        complex_id: str,
        axis: EnvironmentAxis,
        limit: int,
    ) -> EnvironmentFeaturesResponse:
        await self._require_complex(complex_id)
        summary_rows = await self.repository.get_summaries(complex_id)
        axis_summary = self._build_axis_summary(AXIS_BY_KEY[axis], summary_rows)
        total_count, rows = await self.repository.list_axis_features(
            complex_id,
            AXIS_BY_KEY[axis].access_groups,
            limit,
        )
        items = [self._feature_from_row(axis, row) for row in rows]
        return EnvironmentFeaturesResponse(
            meta=self._meta(summary_rows),
            apartment_complex_id=complex_id,
            axis=axis,
            status=axis_summary.status,
            total_count=total_count,
            items=items,
        )

    async def _require_complex(self, complex_id: str) -> Mapping[str, Any]:
        complex_row = await self.repository.get_complex(complex_id)
        if not complex_row:
            raise EnvironmentNotFoundError(complex_id)
        return complex_row

    def _build_axis_summaries(self, summary_rows: list[Mapping[str, Any]]) -> list[AxisSummary]:
        return [self._build_axis_summary(definition, summary_rows) for definition in AXIS_DEFINITIONS]

    def _build_axis_summary(
        self,
        definition: AxisDefinition,
        summary_rows: Iterable[Mapping[str, Any]],
    ) -> AxisSummary:
        row_by_group = {str(row["access_group"]): row for row in summary_rows}
        rows = [row_by_group[group] for group in definition.access_groups if group in row_by_group]
        if not rows:
            return AxisSummary(
                axis=definition.axis,
                label=definition.label,
                status=AxisStatus.UNAVAILABLE,
                empty_reason="summary_not_loaded",
            )

        nearest_by_group = {
            group: nearest_from_summary_row(row_by_group[group]) if group in row_by_group else None
            for group in definition.access_groups
        }
        nearest = nearest_by_group.get(definition.preferred_nearest_group or "")
        if nearest is None:
            candidates = [candidate for candidate in nearest_by_group.values() if candidate]
            nearest = min(
                candidates,
                key=lambda candidate: (
                    candidate.walk_time_minutes is None,
                    candidate.walk_time_minutes or float("inf"),
                    candidate.walk_distance_meters or float("inf"),
                    candidate.feature_id,
                ),
                default=None,
            )

        metrics: dict[str, Any] = {}
        sources: list[SourceReference] = []
        flags: list[str] = []
        failure_reason: str | None = None
        for group, row in row_by_group.items():
            if group not in definition.access_groups:
                continue
            parts = group.split("_")
            prefix = parts[0] + "".join(part.title() for part in parts[1:])
            metrics[f"{prefix}CountWithin5WalkMinutes"] = int(row["count_within_5min"])
            metrics[f"{prefix}CountWithin10WalkMinutes"] = int(row["count_within_10min"])
            metrics[f"{prefix}CountWithin15WalkMinutes"] = int(row["count_within_15min"])
            metrics[f"{prefix}SelectedFeatureCount"] = int(row["selected_feature_count"])
            metrics.update(as_json_object(row.get("metrics")))
            source = source_from_row(row, prefix="nearest_")
            if source and source not in sources:
                sources.append(source)
            flags.extend(flag for flag in as_flags(row.get("qa_flags")) if flag not in flags)
            if not failure_reason and row.get("failure_reason"):
                failure_reason = str(row["failure_reason"])

        status_values = {str(row["summary_status"]) for row in rows}
        if definition.axis == EnvironmentAxis.TRANSPORT:
            # The current transport profile has pre-computed access only for
            # the nearest subway exit and bus stop. The full nearby transit
            # marker population has not yet received access rows, so callers
            # must not describe this as a complete transport layer.
            status = AxisStatus.PARTIAL if status_values & {"available", "partial"} else AxisStatus.UNAVAILABLE
        elif status_values <= {"available", "no_facility_within_limit"}:
            status = AxisStatus.AVAILABLE
        elif status_values & {"available", "no_facility_within_limit", "partial"}:
            status = AxisStatus.PARTIAL
        else:
            status = AxisStatus.UNAVAILABLE

        all_empty = status_values == {"no_facility_within_limit"}
        return AxisSummary(
            axis=definition.axis,
            label=definition.label,
            status=status,
            headline=self._headline(definition, row_by_group, nearest_by_group, nearest, status),
            nearest=nearest,
            nearest_by_group=nearest_by_group,
            metrics=metrics,
            empty_reason="no_feature_within_threshold" if all_empty else None,
            failure_reason=failure_reason,
            qa_flags=flags,
            sources=sources,
        )

    @staticmethod
    def _headline(
        definition: AxisDefinition,
        row_by_group: Mapping[str, Mapping[str, Any]],
        nearest_by_group: Mapping[str, NearestFeature | None],
        nearest: NearestFeature | None,
        status: AxisStatus,
    ) -> str | None:
        """Build concise card copy from stored walking-access facts only."""
        if status == AxisStatus.UNAVAILABLE:
            return None

        def count_within_10(group: str) -> int | None:
            row = row_by_group.get(group)
            return int(row["count_within_10min"]) if row is not None else None

        def nearest_minutes(group: str) -> int | None:
            candidate = nearest_by_group.get(group)
            return display_minutes(candidate.walk_time_minutes) if candidate else None

        if definition.axis == EnvironmentAxis.TRANSPORT:
            parts: list[str] = []
            subway_minutes = nearest_minutes("subway_exit")
            if subway_minutes is not None:
                parts.append(f"지하철 도보 {subway_minutes}분")
            bus_row = row_by_group.get("bus_stop")
            if bus_row is not None:
                bus_count = as_json_object(bus_row.get("metrics")).get("busStopCountWithin500WalkMeters")
                if bus_count is not None:
                    parts.append(f"정류장 {int(bus_count)}곳")
            return " · ".join(parts) or "교통 접근성 데이터 확인 중"

        if definition.axis == EnvironmentAxis.PARKS_PLAY:
            parts = []
            park_minutes = nearest_minutes("park")
            if park_minutes is not None:
                parts.append(f"공원 도보 {park_minutes}분")
            playground_count = count_within_10("playground")
            if playground_count is not None:
                parts.append(f"도보 10분 이내 놀이터 {playground_count}곳")
            return " · ".join(parts) or "공원·놀이 시설 없음"

        if definition.axis == EnvironmentAxis.MEDICAL:
            parts = []
            pediatrics_count = count_within_10("pediatrics")
            if pediatrics_count is not None:
                parts.append(f"도보 10분 이내 소아과 {pediatrics_count}곳")
            nearest_distance = display_distance(nearest.walk_distance_meters) if nearest else None
            if nearest_distance is not None:
                parts.append(f"가장 가까운 곳 {nearest_distance}m")
            return " · ".join(parts) or "의료·약국 시설 없음"

        if definition.axis == EnvironmentAxis.EDUCATION_CARE:
            parts = []
            childcare_count = count_within_10("childcare")
            if childcare_count is not None:
                parts.append(f"도보 10분 이내 어린이집 {childcare_count}곳")
            elementary_minutes = nearest_minutes("elementary_school")
            if elementary_minutes is not None:
                parts.append(f"초등학교 도보 {elementary_minutes}분")
            return " · ".join(parts) or "교육·돌봄 시설 없음"

        if definition.axis == EnvironmentAxis.CONVENIENCE:
            row = row_by_group.get("daily_convenience")
            metrics = as_json_object(row.get("metrics")) if row else {}
            count = metrics.get("convenienceCountWithin500WalkMeters")
            mart_name = metrics.get("nearestMartName")
            mart_distance = display_distance(optional_float(metrics.get("nearestMartWalkDistanceMeters")))
            parts = []
            if count is not None:
                parts.append(f"보행 500m 이내 편의시설 {int(count)}곳")
            if mart_name and mart_distance is not None:
                parts.append(f"최근접 마트 {mart_name} {mart_distance}m")
            elif nearest and nearest.walk_distance_meters is not None:
                parts.append(f"가장 가까운 곳 {display_distance(nearest.walk_distance_meters)}m")
            return " · ".join(parts) or "생활편의 시설 없음"

        return None

    @staticmethod
    def _feature_from_row(axis: EnvironmentAxis, row: Mapping[str, Any]) -> EnvironmentFeature:
        source = source_from_row(row)
        if source is None:
            raise RuntimeError(f"Feature {row.get('feature_id')} has no source dataset")
        access_status = str(row.get("access_status") or "unavailable")
        if access_status not in {status.value for status in AccessStatus}:
            access_status = AccessStatus.UNAVAILABLE.value
        return EnvironmentFeature(
            feature_id=str(row["feature_id"]),
            axis=axis,
            feature_type=str(row["feature_type"]),
            name=str(row["name"]) if row.get("name") else None,
            address=str(row["address"]) if row.get("address") else None,
            position=Position(latitude=float(row["latitude"]), longitude=float(row["longitude"])),
            walk_distance_meters=optional_float(row.get("walk_distance_m")),
            walk_time_minutes=optional_float(row.get("walk_time_min")),
            distance_method=str(row.get("distance_method") or "not_calculated"),
            access_status=AccessStatus(access_status),
            source=source,
            attributes=as_json_object(row.get("attributes")),
            qa_flags=as_flags(row.get("qa_flags")),
        )
