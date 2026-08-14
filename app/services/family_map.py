from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from app.repositories.family_map import FamilyMapRepository
from app.repositories.walking_route import WalkingRouteRepository
from app.schemas.family_map import (
    ApartmentCompareInsight,
    ApartmentCompareMetric,
    ApartmentCompareMetricTarget,
    ApartmentCompareResponse,
    ApartmentCompareTarget,
    ApartmentSummary,
    BoundsFeaturesResponse,
    FeatureSummary,
    MapFeature,
    NearbyFeaturesResponse,
)

EARTH_RADIUS_M = 6371000
DEFAULT_CATEGORIES = ["kids", "school", "park", "hospital", "crosswalk", "signal", "cctv", "risk"]
COMPARE_CATEGORIES = ["kids", "school", "crosswalk", "signal", "cctv", "risk"]
MAX_RADIUS_M = 3000
MAX_LIMIT_PER_SOURCE = 5000
CROSSWALK_VISUAL_MERGE_DISTANCE_M = 50
ELEMENTARY_SCHOOL_MARKER_PREFIX = "elementary_schools:"
ELEMENTARY_SCHOOL_ROUTE_PREFIX = "education_elementary_yangcheon:"

METRIC_RULES: Dict[str, Dict[str, str]] = {
    "kids": {
        "label": "어린이시설",
        "unit": "곳",
        "direction": "more_is_positive",
        "target_more": "돌봄·놀이 선택지 많음",
        "base_more": "돌봄·놀이 선택지는 기준 단지가 많음",
        "similar": "시설 수 비슷함",
    },
    "school": {
        "label": "학교",
        "unit": "곳",
        "direction": "more_is_positive",
        "target_more": "학교 선택지 많음",
        "base_more": "학교 선택지는 기준 단지가 많음",
        "similar": "학교 수 비슷함",
    },
    "crosswalk": {
        "label": "횡단보도",
        "unit": "개",
        "direction": "contextual",
        "target_more": "이동 경로 확인 필요",
        "base_more": "횡단 지점은 비교 단지가 단순할 수 있음",
        "similar": "횡단 지점 수 비슷함",
    },
    "signal": {
        "label": "보행신호",
        "unit": "개",
        "direction": "more_is_positive",
        "target_more": "보호 횡단 가능성 높음",
        "base_more": "보행신호는 기준 단지가 많음",
        "similar": "보행신호 수 비슷함",
    },
    "cctv": {
        "label": "CCTV",
        "unit": "대",
        "direction": "contextual",
        "target_more": "안전 인프라 밀도 높음",
        "base_more": "CCTV 밀도는 기준 단지가 높음",
        "similar": "CCTV 밀도 비슷함",
    },
    "risk": {
        "label": "주의구간",
        "unit": "곳",
        "direction": "less_is_positive",
        "target_more": "확인된 주의구간 많음",
        "base_more": "확인된 주의구간 적음",
        "similar": "주의구간 수 비슷함",
    },
}


@dataclass(frozen=True)
class SourceConfig:
    category: str
    source: str
    table: str
    select: str
    id_column: str
    name_column: str
    lat_column: str
    lng_column: str
    address_column: Optional[str] = None
    geometry_column: Optional[str] = None
    metadata_columns: tuple[str, ...] = ()
    filter_params: tuple[tuple[str, str], ...] = ()
    use_raw_id: bool = False

    @property
    def compact_select(self) -> str:
        columns = [
            self.id_column,
            self.name_column,
            self.lat_column,
            self.lng_column,
        ]
        if self.address_column:
            columns.append(self.address_column)
        return ",".join(dict.fromkeys(columns))


SOURCE_CONFIGS = [
    SourceConfig(
        # These records use the same normalized IDs as the stored walking
        # routes.  Keeping that ID all the way to the map avoids a second
        # source-ID translation for child-care and kindergarten markers.
        category="kids",
        source="education_care",
        table="environment_feature",
        select="feature_id,name,address,latitude,longitude,feature_type,source_dataset_id",
        id_column="feature_id",
        name_column="name",
        address_column="address",
        lat_column="latitude",
        lng_column="longitude",
        metadata_columns=("feature_type", "source_dataset_id"),
        filter_params=(
            ("feature_type", "in.(childcare,kindergarten)"),
            ("map_visible", "eq.true"),
            # An older child-care import remains in the normalized table, but
            # it does not have matching pre-computed routes.  Serve only the
            # current datasets whose feature IDs are route-table foreign keys.
            ("source_dataset_id", "in.(education_childcare_yangcheon_20260731,education_kindergarten_yangcheon)"),
        ),
        use_raw_id=True,
    ),
    SourceConfig(
        category="kids",
        source="playground_facilities",
        table="playground_facilities_yangcheon_processed",
        select="facility_code,facility_name,address,latitude,longitude,facility_category_code,facility_operation_code,facility_owner_code,installed_date",
        id_column="facility_code",
        name_column="facility_name",
        address_column="address",
        lat_column="latitude",
        lng_column="longitude",
        metadata_columns=("facility_category_code", "facility_operation_code", "facility_owner_code", "installed_date"),
    ),
    SourceConfig(
        category="school",
        source="elementary_schools",
        table="elementary_schools_yangcheon_processed",
        select="school_code,school_name,road_address,latitude,longitude,establishment_type,phone_number,homepage_url,established_date",
        id_column="school_code",
        name_column="school_name",
        address_column="road_address",
        lat_column="latitude",
        lng_column="longitude",
        metadata_columns=("establishment_type", "phone_number", "homepage_url", "established_date"),
    ),
    SourceConfig(
        # Use the normalized IDs from the access dataset so a selected park
        # can use the same stored-route lookup as schools and child-care.
        category="park",
        source="environment_parks",
        table="environment_feature",
        select="feature_id,name,address,latitude,longitude,feature_type,attributes,source_dataset_id",
        id_column="feature_id",
        name_column="name",
        address_column="address",
        lat_column="latitude",
        lng_column="longitude",
        metadata_columns=("feature_type", "attributes", "source_dataset_id"),
        filter_params=(
            ("axis", "eq.parks_play"),
            ("feature_type", "eq.park"),
            ("map_visible", "eq.true"),
            ("source_dataset_id", "eq.leisure_parks_sinjeong_nearby_2026h1"),
        ),
        use_raw_id=True,
    ),
    SourceConfig(
        category="hospital",
        source="environment_medical",
        table="environment_feature",
        select="feature_id,name,address,latitude,longitude,feature_type,service_types,attributes,source_dataset_id",
        id_column="feature_id",
        name_column="name",
        address_column="address",
        lat_column="latitude",
        lng_column="longitude",
        metadata_columns=("feature_type", "service_types", "attributes", "source_dataset_id"),
        filter_params=(
            ("axis", "eq.medical"),
            ("feature_type", "eq.medical_clinic"),
            ("map_visible", "eq.true"),
            # Reuse the IDs in complex_feature_access so marker clicks can
            # retrieve the pre-computed walking route without translation.
            ("source_dataset_id", "eq.healthcare_hospitals_seoul"),
        ),
        use_raw_id=True,
    ),
    SourceConfig(
        category="crosswalk",
        source="crosswalk_locations",
        table="crosswalk_locations_yangcheon_processed",
        select="source_row_number,display_name,latitude,longitude,node_link_type,emd_name,geometry_type,geometry_geojson,link_length",
        id_column="source_row_number",
        name_column="display_name",
        lat_column="latitude",
        lng_column="longitude",
        geometry_column="geometry_geojson",
        metadata_columns=("node_link_type", "emd_name", "geometry_type", "link_length"),
    ),
    SourceConfig(
        category="signal",
        source="floor_pedestrian_signals",
        table="floor_pedestrian_signals_yangcheon_processed",
        select="management_number,display_name,estimated_latitude,estimated_longitude,established_date,changed_date,dong_code",
        id_column="management_number",
        name_column="display_name",
        lat_column="estimated_latitude",
        lng_column="estimated_longitude",
        metadata_columns=("established_date", "changed_date", "dong_code"),
    ),
    SourceConfig(
        category="cctv",
        source="cctv",
        table="cctv_yangcheon_processed",
        select="management_number,display_address,latitude,longitude,purpose_type,camera_count,camera_pixel_count,filming_direction_info,installed_year_month",
        id_column="management_number",
        name_column="display_address",
        address_column="display_address",
        lat_column="latitude",
        lng_column="longitude",
        metadata_columns=("purpose_type", "camera_count", "camera_pixel_count", "filming_direction_info", "installed_year_month"),
    ),
    SourceConfig(
        category="risk",
        source="child_safety_zones",
        table="child_safety_zones_yangcheon_processed",
        select="source_row_number,display_name,full_road_address,latitude,longitude,facility_type,designated_year,administrative_dong",
        id_column="source_row_number",
        name_column="display_name",
        address_column="full_road_address",
        lat_column="latitude",
        lng_column="longitude",
        metadata_columns=("facility_type", "designated_year", "administrative_dong"),
    ),
]


def parse_categories(value: Optional[str]) -> List[str]:
    if not value:
        return list(DEFAULT_CATEGORIES)

    requested = [item.strip() for item in value.split(",") if item.strip()]
    return [category for category in DEFAULT_CATEGORIES if category in requested]


def to_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(float(value))


def apartment_name(row: Dict[str, Any]) -> str:
    for key in (
        "name",
        "complex_name_official_price",
        "complex_name_road_address",
        "complex_name_building_register",
    ):
        value = row.get(key)
        if value:
            return str(value)
    return apartment_address(row)


def apartment_address(row: Dict[str, Any]) -> str:
    for key in ("road_address", "parcel_address", "address"):
        value = row.get(key)
        if value:
            return str(value)
    return "주소 정보 없음"


def normalize_apartment(row: Dict[str, Any]) -> ApartmentSummary:
    return ApartmentSummary(
        id=str(row["complex_id"]),
        name=apartment_name(row),
        address=apartment_address(row),
        latitude=float(row["latitude"]),
        longitude=float(row["longitude"]),
        approval_date=row.get("approval_date"),
        household_count=to_int(row.get("household_count")),
        building_count=to_int(row.get("building_count")),
    )


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def radius_to_bounds(latitude: float, longitude: float, radius_m: int) -> Dict[str, float]:
    lat_delta = radius_m / 111320
    lng_delta = radius_m / (111320 * math.cos(math.radians(latitude)))
    return {
        "sw_lat": latitude - lat_delta,
        "sw_lng": longitude - lng_delta,
        "ne_lat": latitude + lat_delta,
        "ne_lng": longitude + lng_delta,
    }


def normalize_feature(
    config: SourceConfig,
    row: Dict[str, Any],
    origin_lat: Optional[float] = None,
    origin_lng: Optional[float] = None,
    compact: bool = False,
) -> MapFeature:
    latitude = float(row[config.lat_column])
    longitude = float(row[config.lng_column])
    metadata = {} if compact else {
        column: row.get(column)
        for column in config.metadata_columns
        if row.get(column) is not None
    }
    distance_m = None
    if origin_lat is not None and origin_lng is not None:
        distance_m = round(haversine_m(origin_lat, origin_lng, latitude, longitude), 1)

    return MapFeature(
        id=str(row[config.id_column]) if config.use_raw_id else f"{config.source}:{row[config.id_column]}",
        category=config.category,
        source=config.source,
        name=str(row[config.name_column]),
        address=row.get(config.address_column) if config.address_column else None,
        latitude=latitude,
        longitude=longitude,
        distance_m=distance_m,
        geometry=None if compact else row.get(config.geometry_column) if config.geometry_column else None,
        metadata=metadata,
    )


def stored_walking_route_feature_id(feature: MapFeature) -> str:
    """Translate legacy school marker IDs to the normalized route-table key."""
    if feature.id.startswith(ELEMENTARY_SCHOOL_MARKER_PREFIX):
        return ELEMENTARY_SCHOOL_ROUTE_PREFIX + feature.id.removeprefix(ELEMENTARY_SCHOOL_MARKER_PREFIX)
    return feature.id


def summarize(features: Iterable[MapFeature]) -> List[FeatureSummary]:
    counts = {category: 0 for category in DEFAULT_CATEGORIES}
    for feature in features:
        counts[feature.category] += 1
    return [
        FeatureSummary(category=category, count=count)
        for category, count in counts.items()
        if count > 0
    ]


def summary_to_metrics(summary: Iterable[FeatureSummary]) -> Dict[str, int]:
    values = {category: 0 for category in COMPARE_CATEGORIES}
    for item in summary:
        if item.category in values:
            values[item.category] = item.count
    return values


def compare_state(base_count: int, target_count: int) -> str:
    diff = target_count - base_count
    tolerance = max(2, round(max(base_count, target_count) * 0.1))
    if abs(diff) <= tolerance:
        return "similar"
    if diff > 0:
        return "target_more"
    return "base_more"


def metric_tone(metric_code: str, state: str) -> str:
    direction = METRIC_RULES[metric_code]["direction"]
    if state == "similar":
        return "neutral"
    if direction == "more_is_positive":
        return "positive" if state == "target_more" else "caution"
    if direction == "less_is_positive":
        return "caution" if state == "target_more" else "positive"
    return "context"


def metric_description(metric_code: str, base_count: int, target_count: int) -> str:
    rule = METRIC_RULES[metric_code]
    state = compare_state(base_count, target_count)
    return rule[state]


def build_metric_rows(
    base_metrics: Dict[str, int],
    target_results: List[ApartmentCompareTarget],
) -> List[ApartmentCompareMetric]:
    rows: List[ApartmentCompareMetric] = []
    for metric_code in COMPARE_CATEGORIES:
        rule = METRIC_RULES[metric_code]
        base_count = base_metrics[metric_code]
        targets = []
        for result in target_results:
            target_count = result.metrics[metric_code]
            state = compare_state(base_count, target_count)
            targets.append(
                ApartmentCompareMetricTarget(
                    apartment_id=result.apartment.id,
                    count=target_count,
                    diff=target_count - base_count,
                    comparison=state,
                    label=rule[state],
                    tone=metric_tone(metric_code, state),
                )
            )
        rows.append(
            ApartmentCompareMetric(
                code=metric_code,
                label=rule["label"],
                unit=rule["unit"],
                base_count=base_count,
                targets=targets,
            )
        )
    return rows


def build_insights(base_metrics: Dict[str, int], target_metrics: Dict[str, int]) -> List[ApartmentCompareInsight]:
    insights: List[ApartmentCompareInsight] = []
    education_codes = [
        code for code in ("kids", "school")
        if compare_state(base_metrics[code], target_metrics[code]) == "target_more"
    ]
    if education_codes:
        insights.append(
            ApartmentCompareInsight(
                category="education",
                title="교육·돌봄 선택지 많음",
                description="기준 아파트보다 1km 이내 어린이시설 또는 학교 수가 더 많습니다.",
                tone="positive",
                metric_codes=education_codes,
            )
        )

    walking_codes = []
    if compare_state(base_metrics["signal"], target_metrics["signal"]) == "target_more":
        walking_codes.append("signal")
    if compare_state(base_metrics["crosswalk"], target_metrics["crosswalk"]) == "target_more":
        walking_codes.append("crosswalk")
    if walking_codes:
        descriptions = []
        if "signal" in walking_codes:
            descriptions.append("보행신호 수가 더 많아 보호 횡단 가능성이 높게 확인됩니다.")
        if "crosswalk" in walking_codes:
            descriptions.append("횡단보도 수가 많아 실제 등하교 동선의 복잡도도 함께 확인하는 것이 좋습니다.")
        insights.append(
            ApartmentCompareInsight(
                category="walking",
                title="보행 조건 확인 필요",
                description=" ".join(descriptions),
                tone="context",
                metric_codes=walking_codes,
            )
        )

    safety_codes = []
    if compare_state(base_metrics["cctv"], target_metrics["cctv"]) == "target_more":
        safety_codes.append("cctv")
    if compare_state(base_metrics["risk"], target_metrics["risk"]) == "base_more":
        safety_codes.append("risk")
    if safety_codes:
        descriptions = []
        if "cctv" in safety_codes:
            descriptions.append("CCTV 수가 더 많아 안전 인프라 밀도가 높게 확인됩니다.")
        if "risk" in safety_codes:
            descriptions.append("확인된 주의구간 수는 기준 아파트보다 적습니다.")
        insights.append(
            ApartmentCompareInsight(
                category="safety",
                title="생활 안전 지표 우세",
                description=" ".join(descriptions),
                tone="positive",
                metric_codes=safety_codes,
            )
        )

    caution_codes = [
        code for code in ("risk",)
        if compare_state(base_metrics[code], target_metrics[code]) == "target_more"
    ]
    if caution_codes:
        insights.append(
            ApartmentCompareInsight(
                category="safety",
                title="주의구간 확인 필요",
                description="확인된 주의구간 수가 기준 아파트보다 많아 실제 생활 동선과 함께 판단하는 것이 좋습니다.",
                tone="caution",
                metric_codes=caution_codes,
            )
        )

    if not insights:
        insights.append(
            ApartmentCompareInsight(
                category="overall",
                title="주요 지표 유사",
                description="기준 아파트와 비교 아파트의 1km 이내 주요 생활환경 지표가 전반적으로 비슷합니다.",
                tone="neutral",
                metric_codes=[],
            )
        )
    return insights


def build_target_summary(base_name: str, target_name: str, insights: List[ApartmentCompareInsight]) -> str:
    positive = [item for item in insights if item.tone == "positive"]
    context = [item for item in insights if item.tone == "context"]
    caution = [item for item in insights if item.tone == "caution"]

    if positive and (context or caution):
        second = context[0] if context else caution[0]
        return (
            f"{target_name}은 {positive[0].title} 조건이 {base_name}보다 더 두드러집니다. "
            f"다만 {second.title} 항목은 실제 이동 경로와 함께 확인하는 것이 좋습니다."
        )
    if positive:
        return f"{target_name}은 {positive[0].title} 조건이 {base_name}보다 더 두드러집니다."
    if context:
        return f"{target_name}은 {context[0].title} 항목을 중심으로 실제 생활 동선을 확인하는 것이 좋습니다."
    if caution:
        return f"{target_name}은 {caution[0].title} 항목을 중심으로 실제 생활 동선을 확인하는 것이 좋습니다."
    return f"{target_name}과 {base_name}은 주요 생활환경 지표가 전반적으로 비슷하게 확인됩니다."


def dedupe_visual_crosswalks(features: List[MapFeature]) -> List[MapFeature]:
    crosswalks: List[MapFeature] = []
    others: List[MapFeature] = []

    for feature in features:
        if feature.source == "crosswalk_locations":
            crosswalks.append(feature)
        else:
            others.append(feature)

    kept_crosswalks: List[MapFeature] = []
    for feature in sorted(crosswalks, key=lambda item: (item.latitude, item.longitude, item.id)):
        if any(
            haversine_m(feature.latitude, feature.longitude, kept.latitude, kept.longitude)
            <= CROSSWALK_VISUAL_MERGE_DISTANCE_M
            for kept in kept_crosswalks
        ):
            continue
        kept_crosswalks.append(feature)

    return [*others, *kept_crosswalks]


def cluster_grid_meters(zoom: int) -> int:
    if zoom <= 11:
        return 2000
    if zoom <= 12:
        return 1000
    if zoom <= 13:
        return 500
    if zoom <= 14:
        return 250
    if zoom <= 15:
        return 150
    if zoom <= 16:
        return 100
    return 0


def cluster_features_for_zoom(features: List[MapFeature], zoom: int) -> List[MapFeature]:
    grid_meters = cluster_grid_meters(zoom)
    if grid_meters == 0:
        return features

    buckets: Dict[str, List[MapFeature]] = {}
    for feature in features:
        lat_grid = grid_meters / 111320
        lng_grid = grid_meters / (111320 * math.cos(math.radians(feature.latitude)))
        lat_key = round(feature.latitude / lat_grid)
        lng_key = round(feature.longitude / lng_grid)
        key = f"{lat_key}:{lng_key}"
        buckets.setdefault(key, []).append(feature)

    clustered: List[MapFeature] = []
    for key, bucket in buckets.items():
        if len(bucket) == 1:
            clustered.append(bucket[0])
            continue

        category = bucket[0].category
        latitude = sum(feature.latitude for feature in bucket) / len(bucket)
        longitude = sum(feature.longitude for feature in bucket) / len(bucket)
        clustered.append(
            MapFeature(
                id=f"cluster:{key}",
                category=category,
                source="cluster",
                name=f"{len(bucket)}개 지점",
                latitude=latitude,
                longitude=longitude,
                address=None,
                distance_m=None,
                geometry=None,
                metadata={"count": len(bucket), "grid_meters": grid_meters},
            )
        )
    return clustered


class FamilyMapService:
    def __init__(
        self,
        repository: Optional[FamilyMapRepository] = None,
        walking_route_repository: Optional[WalkingRouteRepository] = None,
    ) -> None:
        self.repository = repository or FamilyMapRepository()
        self.walking_route_repository = walking_route_repository

    async def search_apartments(self, query: Optional[str], limit: int) -> List[ApartmentSummary]:
        normalized_query = query.strip().lower() if query else ""
        rows = await self.repository.search_apartments(query, limit)
        apartments = [normalize_apartment(row) for row in rows]
        if normalized_query:
            apartments = [
                apartment
                for apartment in apartments
                if normalized_query in apartment.name.lower()
            ]
        return apartments[:limit]

    async def get_nearby_features(
        self,
        complex_id: str,
        radius_m: int,
        categories: Optional[str],
        limit_per_source: int,
    ) -> NearbyFeaturesResponse:
        radius = min(max(radius_m, 1), MAX_RADIUS_M)
        apartment_row = await self.repository.get_apartment(complex_id)
        if not apartment_row:
            raise LookupError("Apartment not found.")

        apartment = normalize_apartment(apartment_row)
        bounds = radius_to_bounds(apartment.latitude, apartment.longitude, radius)
        selected_categories = parse_categories(categories)
        features = await self._fetch_features_in_bounds(
            selected_categories=selected_categories,
            sw_lat=bounds["sw_lat"],
            sw_lng=bounds["sw_lng"],
            ne_lat=bounds["ne_lat"],
            ne_lng=bounds["ne_lng"],
            limit_per_source=limit_per_source,
            origin_lat=apartment.latitude,
            origin_lng=apartment.longitude,
        )
        filtered = [
            feature
            for feature in features
            if feature.distance_m is not None and feature.distance_m <= radius
        ]
        await self._attach_stored_walking_summaries(complex_id, filtered)
        filtered.sort(key=lambda feature: (feature.category, feature.distance_m or 0))
        return NearbyFeaturesResponse(
            apartment=apartment,
            radius_m=radius,
            categories=selected_categories,
            summary=summarize(filtered),
            features=filtered,
        )

    async def _attach_stored_walking_summaries(
        self,
        complex_id: str,
        features: List[MapFeature],
    ) -> None:
        route_feature_ids = [
            stored_walking_route_feature_id(feature)
            for feature in features
            if feature.source in {"elementary_schools", "education_care", "environment_parks"}
        ]
        medical_feature_exists = any(feature.source == "environment_medical" for feature in features)
        if not route_feature_ids and not medical_feature_exists:
            return
        repository = self.walking_route_repository
        if repository is None:
            try:
                repository = WalkingRouteRepository()
            except RuntimeError:
                return
        summaries: dict[str, dict[str, object]] = {}
        if route_feature_ids:
            try:
                summaries = await repository.get_latest_route_summaries(
                    complex_id=complex_id,
                    feature_ids=route_feature_ids,
                )
            except RuntimeError:
                pass
        compact_summaries: dict[str, dict[str, object]] = {}
        compact_summary_reader = getattr(repository, "get_latest_access_summaries", None)
        if medical_feature_exists and compact_summary_reader:
            try:
                compact_summaries = await compact_summary_reader(
                    complex_id=complex_id,
                    access_group="medical_clinic",
                )
            except RuntimeError:
                pass
        for feature in features:
            feature_id = stored_walking_route_feature_id(feature)
            summary = summaries.get(feature_id) or compact_summaries.get(feature_id)
            if not summary:
                continue
            try:
                feature.walking_distance_m = float(summary["walk_distance_m"])
                feature.walking_time_min = float(summary["walk_time_min"])
            except (KeyError, TypeError, ValueError):
                continue

    async def get_features_in_bounds(
        self,
        sw_lat: float,
        sw_lng: float,
        ne_lat: float,
        ne_lng: float,
        categories: Optional[str],
        zoom: int,
        limit_per_source: int,
    ) -> BoundsFeaturesResponse:
        selected_categories = parse_categories(categories)
        features = await self._fetch_features_in_bounds(
            selected_categories=selected_categories,
            sw_lat=sw_lat,
            sw_lng=sw_lng,
            ne_lat=ne_lat,
            ne_lng=ne_lng,
            limit_per_source=limit_per_source,
            compact=True,
        )
        summary = summarize(features)
        display_features = cluster_features_for_zoom(features, zoom)
        return BoundsFeaturesResponse(
            bounds={
                "sw_lat": sw_lat,
                "sw_lng": sw_lng,
                "ne_lat": ne_lat,
                "ne_lng": ne_lng,
            },
            categories=selected_categories,
            summary=summary,
            features=display_features,
        )

    async def compare_apartments(
        self,
        base_apartment_id: str,
        target_apartment_ids: List[str],
        radius_m: int,
    ) -> ApartmentCompareResponse:
        target_ids = list(dict.fromkeys(target_apartment_ids))[:2]
        if not target_ids:
            raise ValueError("At least one target apartment is required.")
        if base_apartment_id in target_ids:
            raise ValueError("Base apartment cannot be used as a comparison target.")

        radius = min(max(radius_m, 1), MAX_RADIUS_M)
        responses = await asyncio.gather(
            self.get_nearby_features(
                complex_id=base_apartment_id,
                radius_m=radius,
                categories=",".join(COMPARE_CATEGORIES),
                limit_per_source=MAX_LIMIT_PER_SOURCE,
            ),
            *[
                self.get_nearby_features(
                    complex_id=target_id,
                    radius_m=radius,
                    categories=",".join(COMPARE_CATEGORIES),
                    limit_per_source=MAX_LIMIT_PER_SOURCE,
                )
                for target_id in target_ids
            ],
        )

        base_response = responses[0]
        base_metrics = summary_to_metrics(base_response.summary)
        target_results: List[ApartmentCompareTarget] = []
        summaries: List[str] = []

        for response in responses[1:]:
            target_metrics = summary_to_metrics(response.summary)
            insights = build_insights(base_metrics, target_metrics)
            summary = build_target_summary(base_response.apartment.name, response.apartment.name, insights)
            summaries.append(summary)
            target_results.append(
                ApartmentCompareTarget(
                    apartment=response.apartment,
                    metrics=target_metrics,
                    summary=summary,
                    insights=insights,
                )
            )

        return ApartmentCompareResponse(
            base=base_response.apartment,
            radius_m=radius,
            categories=list(COMPARE_CATEGORIES),
            base_metrics=base_metrics,
            targets=target_results,
            metrics=build_metric_rows(base_metrics, target_results),
            summary=summaries,
        )

    async def _fetch_features_in_bounds(
        self,
        selected_categories: List[str],
        sw_lat: float,
        sw_lng: float,
        ne_lat: float,
        ne_lng: float,
        limit_per_source: int,
        origin_lat: Optional[float] = None,
        origin_lng: Optional[float] = None,
        compact: bool = False,
    ) -> List[MapFeature]:
        limit = min(max(limit_per_source, 1), MAX_LIMIT_PER_SOURCE)

        selected_configs = [
            config for config in SOURCE_CONFIGS if config.category in selected_categories
        ]
        fetches = [
            self.repository.fetch_bbox(
                table=config.table,
                select=config.compact_select if compact else config.select,
                lat_column=config.lat_column,
                lng_column=config.lng_column,
                sw_lat=sw_lat,
                sw_lng=sw_lng,
                ne_lat=ne_lat,
                ne_lng=ne_lng,
                limit=limit,
                filters=config.filter_params,
            )
            for config in selected_configs
        ]
        rows_by_config = zip(selected_configs, await asyncio.gather(*fetches))

        features: List[MapFeature] = []
        for config, rows in rows_by_config:
            for row in rows:
                features.append(normalize_feature(config, row, origin_lat, origin_lng, compact))
        return dedupe_visual_crosswalks(features)
