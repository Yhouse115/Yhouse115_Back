from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from app.repositories.family_map import FamilyMapRepository
from app.schemas.family_map import (
    ApartmentSummary,
    BoundsFeaturesResponse,
    FeatureSummary,
    MapFeature,
    NearbyFeaturesResponse,
)

EARTH_RADIUS_M = 6371000
DEFAULT_CATEGORIES = ["kids", "school", "park", "hospital", "crosswalk", "signal", "cctv", "risk"]
MAX_RADIUS_M = 3000
MAX_LIMIT_PER_SOURCE = 5000
CROSSWALK_VISUAL_MERGE_DISTANCE_M = 50


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
        select="feature_id,name,address,latitude,longitude,feature_type,attributes,source_dataset_id",
        id_column="feature_id",
        name_column="name",
        address_column="address",
        lat_column="latitude",
        lng_column="longitude",
        metadata_columns=("feature_type", "attributes", "source_dataset_id"),
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


def summarize(features: Iterable[MapFeature]) -> List[FeatureSummary]:
    counts = {category: 0 for category in DEFAULT_CATEGORIES}
    for feature in features:
        counts[feature.category] += 1
    return [
        FeatureSummary(category=category, count=count)
        for category, count in counts.items()
        if count > 0
    ]


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
    def __init__(self, repository: Optional[FamilyMapRepository] = None) -> None:
        self.repository = repository or FamilyMapRepository()

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
        filtered.sort(key=lambda feature: (feature.category, feature.distance_m or 0))
        return NearbyFeaturesResponse(
            apartment=apartment,
            radius_m=radius,
            categories=selected_categories,
            summary=summarize(filtered),
            features=filtered,
        )

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
