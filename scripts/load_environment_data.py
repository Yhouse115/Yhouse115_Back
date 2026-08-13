"""Validate and import five-axis environment API serving data.

The input CSV files are generated outside the backend source tree.  This
script deliberately imports their normalized facilities and pre-computed
walking results instead of calculating straight-line distances at request time.

For a local PostGIS container, emit an idempotent import stream:

    python scripts/load_environment_data.py --emit-psql |
      docker exec -i whyhouse-database psql -v ON_ERROR_STOP=1 -U whyhouse -d whyhouse
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping, TextIO


BACKEND_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = BACKEND_ROOT.parents[2]

COMPLEX_PROFILE_PATH = WORKSPACE_ROOT / "work" / "07_yangcheon_gu" / "05_integration" / "complex_transport_profile.csv"
FEATURES_PATH = WORKSPACE_ROOT / "data" / "processed" / "environment" / "pois" / "environment_features.csv"
ACCESS_PATH = WORKSPACE_ROOT / "data" / "processed" / "environment" / "complex_environment_access.csv"
SUMMARY_PATH = WORKSPACE_ROOT / "data" / "processed" / "environment" / "complex_environment_summary.csv"
SOURCE_MANIFEST_PATH = WORKSPACE_ROOT / "work" / "09_environment" / "source_manifest.csv"
BUS_STOPS_PATH = WORKSPACE_ROOT / "data" / "processed" / "transit" / "yangcheon_bus_stops.csv"
TRANSIT_STOPS_PATH = WORKSPACE_ROOT / "work" / "07_yangcheon_gu" / "02_accessibility" / "transit_stops.geojson"

TRANSPORT_CALCULATION_VERSION = "complex_transport_profile_20260811"
TRANSPORT_POLICY_VERSION = "transport_access_profile_v1"
TRANSPORT_BUS_DATASET_ID = "transit_bus_stops_yangcheon_20260811"
TRANSPORT_SUBWAY_DATASET_ID = "transit_subway_exits_yangcheon_20260811"
TRANSPORT_PROFILE_DATASET_ID = "complex_transport_profile_yangcheon_20260811"

PRIMARY_KEYS: dict[str, tuple[str, ...]] = {
    "source_dataset": ("source_dataset_id",),
    "apartment_complex": ("complex_id",),
    "environment_feature": ("feature_id",),
    "complex_feature_access": (
        "complex_id",
        "feature_id",
        "access_group",
        "main_origin_id",
        "calculation_version",
    ),
    "complex_environment_summary": (
        "complex_id",
        "access_group",
        "calculation_version",
    ),
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def empty_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def to_float(value: str | None, field: str) -> float | None:
    normalized = empty_to_none(value)
    if normalized is None:
        return None
    try:
        return float(normalized)
    except ValueError as exc:
        raise ValueError(f"{field} must be numeric: {value!r}") from exc


def to_int(value: str | None, field: str) -> int | None:
    numeric = to_float(value, field)
    if numeric is None:
        return None
    if not numeric.is_integer():
        raise ValueError(f"{field} must be an integer: {value!r}")
    return int(numeric)


def to_iso_date(value: str | None, field: str) -> str | None:
    normalized = empty_to_none(value)
    if normalized is None:
        return None
    try:
        return date.fromisoformat(normalized).isoformat()
    except ValueError as exc:
        raise ValueError(f"{field} must be YYYY-MM-DD: {value!r}") from exc


def split_flags(value: str | None) -> list[str]:
    return [flag.strip() for flag in (value or "").split("|") if flag.strip()]


def parse_json_object(value: str | None, field: str) -> dict[str, Any]:
    normalized = empty_to_none(value)
    if normalized is None:
        return {}
    try:
        parsed = json.loads(normalized)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field} must be JSON: {value!r}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{field} must be a JSON object")
    return parsed


def feature_service_types(feature_type: str) -> list[str]:
    if feature_type in {"pediatrics", "obstetrics_gynecology", "pharmacy"}:
        return [feature_type]
    return []


def environment_axis(layer_category: str, feature_type: str) -> str:
    """Map normalized ingestion categories to the five public UI axes.

    The raw file also contains safety features. They remain available to the
    legacy safety product, but none of the new environment routes expose that
    axis. Keeping the mapping here makes the database value explicit and
    prevents the API from inferring category membership at request time.
    """
    if layer_category == "education_childcare":
        return "education_care"
    if layer_category == "healthcare":
        return "medical"
    if layer_category == "leisure_environment":
        return "parks_play"
    if layer_category == "transit":
        return "transport"
    if layer_category == "safety":
        return "safety"
    raise ValueError(f"No environment axis mapping for {layer_category}/{feature_type}")


def build_source_datasets(manifest_rows: Iterable[Mapping[str, str]]) -> dict[str, dict[str, Any]]:
    datasets: dict[str, dict[str, Any]] = {}
    for row in manifest_rows:
        dataset_id = empty_to_none(row.get("dataset_id"))
        if not dataset_id:
            continue
        datasets[dataset_id] = {
            "source_dataset_id": dataset_id,
            "source_name": empty_to_none(row.get("dataset_name")) or dataset_id,
            "source_file": empty_to_none(row.get("local_original_path")),
            "source_sha256": empty_to_none(row.get("sha256")),
            "reference_date": empty_to_none(row.get("reference_period_end"))
            or empty_to_none(row.get("reference_period_start")),
            "license_name": empty_to_none(row.get("license")),
            "metadata": json.dumps(
                {
                    "provider": empty_to_none(row.get("provider")),
                    "sourceUrl": empty_to_none(row.get("source_url")),
                    "deliveryMethod": empty_to_none(row.get("delivery_method")),
                    "normalizedPath": empty_to_none(row.get("local_normalized_path")),
                },
                ensure_ascii=False,
            ),
        }
    return datasets


def ensure_dataset(
    datasets: dict[str, dict[str, Any]],
    dataset_id: str,
    *,
    source_name: str | None = None,
    source_file: str | None = None,
    reference_date: str | None = None,
) -> None:
    datasets.setdefault(
        dataset_id,
        {
            "source_dataset_id": dataset_id,
            "source_name": source_name or dataset_id,
            "source_file": source_file,
            "source_sha256": None,
            "reference_date": reference_date,
            "license_name": "unknown",
            "metadata": "{}",
        },
    )


def build_complexes(rows: Iterable[Mapping[str, str]]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for row in rows:
        complex_id = empty_to_none(row.get("complex_id"))
        name = empty_to_none(row.get("complex_name"))
        if not complex_id or not name:
            raise ValueError("Complex profile requires complex_id and complex_name")
        longitude = to_float(row.get("longitude"), "complex.longitude")
        latitude = to_float(row.get("latitude"), "complex.latitude")
        if longitude is None or latitude is None:
            raise ValueError(f"Complex {complex_id} has no coordinates")
        payloads.append(
            {
                "complex_id": complex_id,
                "name": name,
                "admin_dong_code": empty_to_none(row.get("admin_dong_code")),
                "admin_dong_name": empty_to_none(row.get("admin_dong_name")),
                "legal_dong_code": empty_to_none(row.get("legal_dong_code")),
                "road_address": empty_to_none(row.get("road_address")),
                "parcel_address": empty_to_none(row.get("parcel_address")),
                "household_count": to_int(row.get("household_count"), "complex.household_count"),
                "building_count": to_int(row.get("building_count"), "complex.building_count"),
                "approval_date": to_iso_date(row.get("approval_date"), "complex.approval_date"),
                "longitude": longitude,
                "latitude": latitude,
                "coordinate_method": empty_to_none(row.get("coordinate_method")) or "unknown",
                "coordinate_confidence": empty_to_none(row.get("coordinate_confidence")),
                "complex_status": empty_to_none(row.get("complex_status")) or "active",
                "master_reference_date": empty_to_none(row.get("master_reference_date")),
                "qa_flags": split_flags(row.get("qa_flags")),
            }
        )
    return payloads


def build_environment_features(
    rows: Iterable[Mapping[str, str]], datasets: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for row in rows:
        feature_id = empty_to_none(row.get("feature_id"))
        dataset_id = empty_to_none(row.get("source_dataset_id"))
        record_id = empty_to_none(row.get("source_record_id"))
        feature_type = empty_to_none(row.get("feature_type"))
        layer_category = empty_to_none(row.get("layer_category"))
        if not all((feature_id, dataset_id, record_id, feature_type, layer_category)):
            raise ValueError("Environment feature is missing an identifier or category")
        longitude = to_float(row.get("longitude"), f"feature.{feature_id}.longitude")
        latitude = to_float(row.get("latitude"), f"feature.{feature_id}.latitude")
        if longitude is None or latitude is None:
            raise ValueError(f"Environment feature {feature_id} has no coordinates")
        ensure_dataset(datasets, dataset_id)
        payloads.append(
            {
                "feature_id": feature_id,
                "source_dataset_id": dataset_id,
                "source_record_id": record_id,
                "layer_category": layer_category,
                "axis": environment_axis(layer_category, feature_type),
                "feature_type": feature_type,
                "scope_role": "yangcheon",
                "service_types": feature_service_types(feature_type),
                "name": empty_to_none(row.get("name")),
                "address": empty_to_none(row.get("address")),
                "longitude": longitude,
                "latitude": latitude,
                "coordinate_status": empty_to_none(row.get("coordinate_status")) or "unknown",
                "coordinate_method": empty_to_none(row.get("coordinate_method")) or "unknown",
                "record_status": empty_to_none(row.get("record_status")) or "unknown",
                "reference_date": empty_to_none(row.get("reference_date")),
                "attributes": json.dumps(parse_json_object(row.get("attributes_json"), "feature.attributes_json"), ensure_ascii=False),
                "qa_flags": split_flags(row.get("qa_flags")),
            }
        )
    return payloads


def build_transit_features(
    bus_rows: Iterable[Mapping[str, str]],
    transit_geojson: Mapping[str, Any],
    datasets: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    ensure_dataset(
        datasets,
        TRANSPORT_BUS_DATASET_ID,
        source_name="양천구 버스정류장",
        source_file="data/processed/transit/yangcheon_bus_stops.csv",
    )
    ensure_dataset(
        datasets,
        TRANSPORT_SUBWAY_DATASET_ID,
        source_name="양천구 인접 지하철 출입구",
        source_file="work/07_yangcheon_gu/02_accessibility/transit_stops.geojson",
    )

    payloads: dict[str, dict[str, Any]] = {}
    for row in bus_rows:
        stop_id = empty_to_none(row.get("stop_id"))
        if not stop_id:
            raise ValueError("Bus stop is missing stop_id")
        longitude = to_float(row.get("longitude"), f"bus.{stop_id}.longitude")
        latitude = to_float(row.get("latitude"), f"bus.{stop_id}.latitude")
        if longitude is None or latitude is None:
            raise ValueError(f"Bus stop {stop_id} has no coordinates")
        payloads[f"transit_bus_stop:{stop_id}"] = {
            "feature_id": f"transit_bus_stop:{stop_id}",
            "source_dataset_id": TRANSPORT_BUS_DATASET_ID,
            "source_record_id": stop_id,
            "layer_category": "transit",
            "axis": "transport",
            "feature_type": "bus_stop",
            "scope_role": "yangcheon",
            "service_types": [],
            "name": empty_to_none(row.get("stop_name")),
            "address": None,
            "longitude": longitude,
            "latitude": latitude,
            "coordinate_status": empty_to_none(row.get("coordinate_status")) or "unknown",
            "coordinate_method": "source_wgs84",
            "record_status": "active",
            "reference_date": empty_to_none(row.get("reference_date")),
            "attributes": json.dumps(
                {
                    "arsId": empty_to_none(row.get("ars_id")),
                    "stopType": empty_to_none(row.get("stop_type")),
                },
                ensure_ascii=False,
            ),
            "qa_flags": split_flags(row.get("qa_flags")),
        }

    features = transit_geojson.get("features")
    if not isinstance(features, list):
        raise ValueError("Transit GeoJSON must contain features")
    for feature in features:
        if not isinstance(feature, dict):
            raise ValueError("Transit GeoJSON feature must be an object")
        properties = feature.get("properties")
        geometry = feature.get("geometry")
        if not isinstance(properties, dict) or not isinstance(geometry, dict):
            raise ValueError("Transit GeoJSON feature is missing properties or geometry")
        coordinates = geometry.get("coordinates")
        if not isinstance(coordinates, list) or len(coordinates) < 2:
            raise ValueError("Transit GeoJSON requires Point coordinates")
        longitude = float(coordinates[0])
        latitude = float(coordinates[1])

        if properties.get("target_kind") == "bus":
            stop_id = empty_to_none(str(properties.get("target_id") or properties.get("stop_id") or ""))
            if not stop_id:
                raise ValueError("Transit bus feature is missing stop_id")
            feature_id = f"transit_bus_stop:{stop_id}"
            # The Yangcheon-only source is authoritative when it contains the
            # stop. The walking input supplements it with nearby boundary stops
            # that can still be the closest stop for a Yangcheon complex.
            payloads.setdefault(
                feature_id,
                {
                    "feature_id": feature_id,
                    "source_dataset_id": TRANSPORT_BUS_DATASET_ID,
                    "source_record_id": stop_id,
                    "layer_category": "transit",
                    "axis": "transport",
                    "feature_type": "bus_stop",
                    "scope_role": "boundary_support",
                    "service_types": [],
                    "name": empty_to_none(str(properties.get("stop_name") or "")),
                    "address": None,
                    "longitude": longitude,
                    "latitude": latitude,
                    "coordinate_status": "verified_wgs84",
                    "coordinate_method": "accessibility_input_wgs84",
                    "record_status": "active",
                    "reference_date": None,
                    "attributes": json.dumps(
                        {
                            "arsId": empty_to_none(str(properties.get("ars_id") or "")),
                            "stopType": empty_to_none(str(properties.get("stop_type") or "")),
                        },
                        ensure_ascii=False,
                    ),
                    "qa_flags": [],
                },
            )
            continue

        if properties.get("target_kind") != "subway":
            continue
        exit_id = empty_to_none(str(properties.get("exit_id") or ""))
        if not exit_id:
            raise ValueError("Subway exit requires exit_id")
        station_name = empty_to_none(str(properties.get("station_name") or "")) or "지하철"
        payloads[f"transit_subway_exit:{exit_id}"] = {
            "feature_id": f"transit_subway_exit:{exit_id}",
            "source_dataset_id": TRANSPORT_SUBWAY_DATASET_ID,
            "source_record_id": exit_id,
            "layer_category": "transit",
            "axis": "transport",
            "feature_type": "subway_exit",
            "scope_role": "boundary_support",
            "service_types": [],
            "name": f"{station_name} 출입구",
            "address": None,
            "longitude": longitude,
            "latitude": latitude,
            "coordinate_status": "verified_wgs84",
            "coordinate_method": "source_wgs84",
            "record_status": "active",
            "reference_date": None,
            "attributes": json.dumps(
                {
                    "stationName": station_name,
                    "lineName": empty_to_none(str(properties.get("line") or "")),
                    "exitId": exit_id,
                    "stationCode": empty_to_none(str(properties.get("station_code") or "")),
                    "hasLift": properties.get("has_lift") == "1",
                    "hasElevator": properties.get("has_elevator") == "1",
                },
                ensure_ascii=False,
            ),
            "qa_flags": [],
        }
    return list(payloads.values())


def build_environment_access(rows: Iterable[Mapping[str, str]]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for row in rows:
        required = ("complex_id", "feature_id", "access_group", "main_origin_id", "origin_method", "calculation_version")
        if any(not empty_to_none(row.get(field)) for field in required):
            raise ValueError(f"Environment access is missing a required key: {required}")
        payloads.append(
            {
                "complex_id": row["complex_id"],
                "feature_id": row["feature_id"],
                "access_group": row["access_group"],
                "main_origin_id": row["main_origin_id"],
                "origin_method": row["origin_method"],
                "calculation_version": row["calculation_version"],
                "policy_version": empty_to_none(row.get("policy_version")),
                "reference_date": empty_to_none(row.get("reference_date")),
                "straight_distance_m": to_float(row.get("straight_distance_m"), "access.straight_distance_m"),
                "walk_distance_m": to_float(row.get("walk_distance_m"), "access.walk_distance_m"),
                "walk_time_min": to_float(row.get("walk_time_min"), "access.walk_time_min"),
                "distance_method": empty_to_none(row.get("distance_method")) or "not_calculated",
                "access_status": empty_to_none(row.get("access_status")) or "unavailable",
                "category_distance_limit_m": to_float(
                    row.get("category_distance_limit_m"), "access.category_distance_limit_m"
                ),
                "is_nearest": (empty_to_none(row.get("is_nearest")) or "").lower() == "true",
                "selection_reason": empty_to_none(row.get("selection_reason")),
                "failure_reason": empty_to_none(row.get("failure_reason")),
                "qa_flags": split_flags(row.get("qa_flags")),
            }
        )
    return payloads


def build_environment_summaries(rows: Iterable[Mapping[str, str]]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for row in rows:
        required = ("complex_id", "access_group", "main_origin_id", "origin_method", "calculation_version")
        if any(not empty_to_none(row.get(field)) for field in required):
            raise ValueError(f"Environment summary is missing a required key: {required}")
        payloads.append(
            {
                "complex_id": row["complex_id"],
                "access_group": row["access_group"],
                "main_origin_id": row["main_origin_id"],
                "origin_method": row["origin_method"],
                "calculation_version": row["calculation_version"],
                "policy_version": empty_to_none(row.get("policy_version")),
                "reference_date": empty_to_none(row.get("reference_date")),
                "category_distance_limit_m": to_float(
                    row.get("category_distance_limit_m"), "summary.category_distance_limit_m"
                ),
                "nearest_feature_id": empty_to_none(row.get("nearest_feature_id")),
                "nearest_walk_distance_m": to_float(
                    row.get("nearest_walk_distance_m"), "summary.nearest_walk_distance_m"
                ),
                "nearest_walk_time_min": to_float(
                    row.get("nearest_walk_time_min"), "summary.nearest_walk_time_min"
                ),
                "count_within_5min": to_int(row.get("count_within_5min"), "summary.count_within_5min") or 0,
                "count_within_10min": to_int(row.get("count_within_10min"), "summary.count_within_10min") or 0,
                "count_within_15min": to_int(row.get("count_within_15min"), "summary.count_within_15min") or 0,
                "selected_feature_count": to_int(row.get("selected_feature_count"), "summary.selected_feature_count") or 0,
                "metrics": "{}",
                "summary_status": empty_to_none(row.get("summary_status")) or "unavailable",
                "failure_reason": empty_to_none(row.get("failure_reason")),
                "qa_flags": split_flags(row.get("qa_flags")),
            }
        )
    return payloads


def build_transport_rows(
    profile_rows: Iterable[Mapping[str, str]],
    transit_feature_ids: set[str],
    datasets: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ensure_dataset(
        datasets,
        TRANSPORT_PROFILE_DATASET_ID,
        source_name="양천구 단지 교통 프로필",
        source_file="work/07_yangcheon_gu/05_integration/complex_transport_profile.csv",
        reference_date="2026-08-11",
    )
    access_payloads: list[dict[str, Any]] = []
    summary_payloads: list[dict[str, Any]] = []

    for row in profile_rows:
        complex_id = empty_to_none(row.get("complex_id"))
        origin_id = empty_to_none(row.get("main_origin_id"))
        origin_method = empty_to_none(row.get("origin_method"))
        if not all((complex_id, origin_id, origin_method)):
            raise ValueError("Transport profile is missing complex or origin identifiers")
        failure_reason = empty_to_none(row.get("failure_reason"))
        reference_date = empty_to_none(row.get("access_reference_date"))
        qa_flags = split_flags(row.get("qa_flags"))

        subway_exit = empty_to_none(row.get("nearest_subway_exit"))
        subway_feature_id = f"transit_subway_exit:{subway_exit}" if subway_exit else None
        subway_available = bool(subway_feature_id and subway_feature_id in transit_feature_ids)
        if subway_feature_id and not subway_available:
            raise ValueError(f"Transport profile subway exit is absent from transit source: {subway_feature_id}")
        subway_status = "available" if subway_available else "unavailable"
        if subway_available:
            access_payloads.append(
                {
                    "complex_id": complex_id,
                    "feature_id": subway_feature_id,
                    "access_group": "subway_exit",
                    "main_origin_id": origin_id,
                    "origin_method": origin_method,
                    "calculation_version": TRANSPORT_CALCULATION_VERSION,
                    "policy_version": TRANSPORT_POLICY_VERSION,
                    "reference_date": reference_date,
                    "straight_distance_m": to_float(row.get("subway_straight_distance_m"), "transport.subway_straight_distance_m"),
                    "walk_distance_m": to_float(row.get("subway_walk_distance_m"), "transport.subway_walk_distance_m"),
                    "walk_time_min": to_float(row.get("subway_walk_time_min"), "transport.subway_walk_time_min"),
                    "distance_method": "walking_network",
                    "access_status": subway_status,
                    "category_distance_limit_m": None,
                    "is_nearest": True,
                    "selection_reason": "nearest",
                    "failure_reason": failure_reason,
                    "qa_flags": qa_flags,
                }
            )
        summary_payloads.append(
            {
                "complex_id": complex_id,
                "access_group": "subway_exit",
                "main_origin_id": origin_id,
                "origin_method": origin_method,
                "calculation_version": TRANSPORT_CALCULATION_VERSION,
                "policy_version": TRANSPORT_POLICY_VERSION,
                "reference_date": reference_date,
                "category_distance_limit_m": None,
                "nearest_feature_id": subway_feature_id if subway_available else None,
                "nearest_walk_distance_m": to_float(row.get("subway_walk_distance_m"), "transport.subway_walk_distance_m"),
                "nearest_walk_time_min": to_float(row.get("subway_walk_time_min"), "transport.subway_walk_time_min"),
                "count_within_5min": 0,
                "count_within_10min": 0,
                "count_within_15min": 0,
                "selected_feature_count": 1 if subway_available else 0,
                "metrics": json.dumps(
                    {
                        "stationName": empty_to_none(row.get("nearest_subway_station")),
                        "lineName": empty_to_none(row.get("nearest_subway_line")),
                        "exitId": subway_exit,
                    },
                    ensure_ascii=False,
                ),
                "summary_status": subway_status,
                "failure_reason": failure_reason,
                "qa_flags": qa_flags,
            }
        )

        bus_stop_id = empty_to_none(row.get("nearest_bus_stop_id"))
        bus_feature_id = f"transit_bus_stop:{bus_stop_id}" if bus_stop_id else None
        bus_available = bool(bus_feature_id and bus_feature_id in transit_feature_ids)
        if bus_feature_id and not bus_available:
            raise ValueError(f"Transport profile bus stop is absent from bus source: {bus_feature_id}")
        bus_status = "available" if bus_available else "unavailable"
        if bus_available:
            access_payloads.append(
                {
                    "complex_id": complex_id,
                    "feature_id": bus_feature_id,
                    "access_group": "bus_stop",
                    "main_origin_id": origin_id,
                    "origin_method": origin_method,
                    "calculation_version": TRANSPORT_CALCULATION_VERSION,
                    "policy_version": TRANSPORT_POLICY_VERSION,
                    "reference_date": reference_date,
                    "straight_distance_m": None,
                    "walk_distance_m": to_float(row.get("bus_stop_walk_distance_m"), "transport.bus_stop_walk_distance_m"),
                    "walk_time_min": to_float(row.get("bus_stop_walk_time_min"), "transport.bus_stop_walk_time_min"),
                    "distance_method": "walking_network",
                    "access_status": bus_status,
                    "category_distance_limit_m": 500.0,
                    "is_nearest": True,
                    "selection_reason": "nearest",
                    "failure_reason": failure_reason,
                    "qa_flags": qa_flags,
                }
            )
        summary_payloads.append(
            {
                "complex_id": complex_id,
                "access_group": "bus_stop",
                "main_origin_id": origin_id,
                "origin_method": origin_method,
                "calculation_version": TRANSPORT_CALCULATION_VERSION,
                "policy_version": TRANSPORT_POLICY_VERSION,
                "reference_date": reference_date,
                "category_distance_limit_m": 500.0,
                "nearest_feature_id": bus_feature_id if bus_available else None,
                "nearest_walk_distance_m": to_float(row.get("bus_stop_walk_distance_m"), "transport.bus_stop_walk_distance_m"),
                "nearest_walk_time_min": to_float(row.get("bus_stop_walk_time_min"), "transport.bus_stop_walk_time_min"),
                "count_within_5min": 0,
                "count_within_10min": 0,
                "count_within_15min": 0,
                "selected_feature_count": 1 if bus_available else 0,
                "metrics": json.dumps(
                    {
                        "busStopCountWithin500WalkMeters": to_int(
                            row.get("bus_stop_count_500m"), "transport.bus_stop_count_500m"
                        ),
                        "stopName": empty_to_none(row.get("nearest_bus_stop_name")),
                        "routeMethod": empty_to_none(row.get("route_method")),
                    },
                    ensure_ascii=False,
                ),
                "summary_status": bus_status,
                "failure_reason": failure_reason,
                "qa_flags": qa_flags,
            }
        )
    return access_payloads, summary_payloads


def validate_payloads(payloads: Mapping[str, list[dict[str, Any]]]) -> dict[str, int]:
    for table, keys in PRIMARY_KEYS.items():
        rows = payloads.get(table, [])
        if not rows:
            raise ValueError(f"Cannot import an empty table payload: {table}")
        seen: set[tuple[Any, ...]] = set()
        for row in rows:
            key = tuple(row[column] for column in keys)
            if key in seen:
                raise ValueError(f"Duplicate {table} key: {key}")
            seen.add(key)

    complex_ids = {row["complex_id"] for row in payloads["apartment_complex"]}
    feature_ids = {row["feature_id"] for row in payloads["environment_feature"]}
    source_ids = {row["source_dataset_id"] for row in payloads["source_dataset"]}
    missing_feature_datasets = {
        row["source_dataset_id"]
        for row in payloads["environment_feature"]
        if row["source_dataset_id"] not in source_ids
    }
    if missing_feature_datasets:
        raise ValueError(f"Features reference unknown datasets: {sorted(missing_feature_datasets)}")
    for table in ("complex_feature_access", "complex_environment_summary"):
        missing_complexes = {row["complex_id"] for row in payloads[table] if row["complex_id"] not in complex_ids}
        if missing_complexes:
            raise ValueError(f"{table} references unknown complexes: {sorted(missing_complexes)[:5]}")
    missing_access_features = {
        row["feature_id"] for row in payloads["complex_feature_access"] if row["feature_id"] not in feature_ids
    }
    if missing_access_features:
        raise ValueError(f"Access rows reference unknown features: {sorted(missing_access_features)[:5]}")
    missing_summary_features = {
        row["nearest_feature_id"]
        for row in payloads["complex_environment_summary"]
        if row["nearest_feature_id"] and row["nearest_feature_id"] not in feature_ids
    }
    if missing_summary_features:
        raise ValueError(f"Summary rows reference unknown features: {sorted(missing_summary_features)[:5]}")
    return {table: len(rows) for table, rows in payloads.items()}


def build_payloads(workspace_root: Path = WORKSPACE_ROOT) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    paths = {
        "complex_profile": workspace_root / "work" / "07_yangcheon_gu" / "05_integration" / "complex_transport_profile.csv",
        "features": workspace_root / "data" / "processed" / "environment" / "pois" / "environment_features.csv",
        "access": workspace_root / "data" / "processed" / "environment" / "complex_environment_access.csv",
        "summary": workspace_root / "data" / "processed" / "environment" / "complex_environment_summary.csv",
        "source_manifest": workspace_root / "work" / "09_environment" / "source_manifest.csv",
        "bus_stops": workspace_root / "data" / "processed" / "transit" / "yangcheon_bus_stops.csv",
        "transit_stops": workspace_root / "work" / "07_yangcheon_gu" / "02_accessibility" / "transit_stops.geojson",
    }
    for path in paths.values():
        if not path.exists():
            raise FileNotFoundError(f"Required source is missing: {path}")

    profile_rows = read_csv(paths["complex_profile"])
    datasets = build_source_datasets(read_csv(paths["source_manifest"]))
    complexes = build_complexes(profile_rows)
    environment_features = build_environment_features(read_csv(paths["features"]), datasets)
    transit_geojson = json.loads(paths["transit_stops"].read_text(encoding="utf-8"))
    transit_features = build_transit_features(read_csv(paths["bus_stops"]), transit_geojson, datasets)
    all_features = [*environment_features, *transit_features]
    access = build_environment_access(read_csv(paths["access"]))
    summaries = build_environment_summaries(read_csv(paths["summary"]))
    transport_access, transport_summaries = build_transport_rows(
        profile_rows,
        {row["feature_id"] for row in transit_features},
        datasets,
    )
    payloads = {
        "source_dataset": list(datasets.values()),
        "apartment_complex": complexes,
        "environment_feature": all_features,
        "complex_feature_access": [*access, *transport_access],
        "complex_environment_summary": [*summaries, *transport_summaries],
    }
    counts = validate_payloads(payloads)
    qa = {
        "status": "COMPLETE",
        "counts": counts,
        "environment_feature_type_counts": dict(
            Counter(row["feature_type"] for row in environment_features)
        ),
        "transport_feature_count": len(transit_features),
        "source_paths": {key: str(path.relative_to(workspace_root)) for key, path in paths.items()},
    }
    return payloads, qa


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def postgres_array(values: list[str]) -> str:
    escaped = [value.replace("\\", "\\\\").replace('"', '\\"') for value in values]
    return "{" + ",".join(f'"{value}"' for value in escaped) + "}"


def copy_value(value: Any) -> Any:
    if value is None:
        return r"\N"
    if isinstance(value, list):
        return postgres_array([str(item) for item in value])
    return value


def emit_psql_import(payloads: Mapping[str, list[dict[str, Any]]], stream: TextIO) -> None:
    """Write a transactional and idempotent local PostgreSQL import script."""
    stream.write("BEGIN;\n")
    for index, (table, rows) in enumerate(payloads.items(), start=1):
        if not rows:
            raise ValueError(f"Cannot import empty payload: {table}")
        columns = list(rows[0])
        if any(list(row) != columns for row in rows):
            raise ValueError(f"Inconsistent payload columns: {table}")
        keys = PRIMARY_KEYS[table]
        table_sql = quote_identifier(table)
        stage_sql = quote_identifier(f"_environment_import_{index}")
        columns_sql = ", ".join(quote_identifier(column) for column in columns)
        stream.write(
            f"CREATE TEMP TABLE {stage_sql} "
            f"(LIKE public.{table_sql} INCLUDING DEFAULTS) ON COMMIT DROP;\n"
        )
        stream.write(
            f"COPY {stage_sql} ({columns_sql}) FROM STDIN "
            "WITH (FORMAT csv, NULL '\\N');\n"
        )
        writer = csv.writer(stream, lineterminator="\n")
        for row in rows:
            writer.writerow([copy_value(row[column]) for column in columns])
        stream.write("\\.\n")
        updates = [column for column in columns if column not in keys]
        update_sql = ", ".join(
            f"{quote_identifier(column)} = EXCLUDED.{quote_identifier(column)}" for column in updates
        )
        keys_sql = ", ".join(quote_identifier(key) for key in keys)
        stream.write(
            f"INSERT INTO public.{table_sql} ({columns_sql}) "
            f"SELECT {columns_sql} FROM {stage_sql} "
            f"ON CONFLICT ({keys_sql}) DO UPDATE SET {update_sql};\n"
        )
    stream.write("COMMIT;\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and import five-axis environment API serving data")
    parser.add_argument("--workspace-root", type=Path, default=WORKSPACE_ROOT)
    parser.add_argument("--qa-output", type=Path, default=WORKSPACE_ROOT / "work" / "09_environment" / "environment_api_load_qa.json")
    parser.add_argument("--emit-psql", action="store_true", help="Write a local PostgreSQL import script to stdout")
    args = parser.parse_args()
    payloads, qa = build_payloads(args.workspace_root.resolve())
    qa["psql_import_requested"] = args.emit_psql
    qa["apply_status"] = "PSQL_IMPORT_EMITTED" if args.emit_psql else "VALIDATED_NOT_UPLOADED"
    args.qa_output.parent.mkdir(parents=True, exist_ok=True)
    args.qa_output.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.emit_psql:
        emit_psql_import(payloads, sys.stdout)
        print(json.dumps(qa, ensure_ascii=False), file=sys.stderr)
    else:
        print(json.dumps(qa, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
