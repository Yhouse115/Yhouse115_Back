"""Load the five-table environment serving model into the configured Supabase.

The Supabase project already contains normalized map features.  The offline
walking CSV was calculated against an earlier normalized-feature ID scheme, so
this loader maps the same physical facilities by source record first and by
name/coordinate second.  It never calculates route distance during an API
request.

Use a dry run first, then explicitly apply:

    python scripts/load_environment_serving_to_supabase.py
    python scripts/load_environment_serving_to_supabase.py --apply
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import httpx

from app.core.config import settings
from scripts import load_environment_data as offline


WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
PRECOMPUTED_GROUPS = {
    "pediatrics",
    "obstetrics_gynecology",
    "pharmacy",
    "park",
    "playground",
    "childcare",
    "kindergarten",
    "elementary_school",
}
TRANSPORT_CALCULATION_VERSION = "complex_transport_profile_20260811"
TRANSPORT_POLICY_VERSION = "transport_access_profile_v1"
SUBWAY_EXIT_DATASET_ID = "transit_subway_exits_yangcheon_20260811"
BOUNDARY_BUS_DATASET_ID = "transit_bus_boundary_support_yangcheon_20260811"
SOURCE_NAME_OVERRIDES = {
    "bus_stops_yangcheon": "양천구 버스정류장",
    "childcare_centers_yangcheon": "양천구 어린이집",
    "commercial_stores_yangcheon": "양천구 생활상업시설",
    "elementary_schools_yangcheon": "양천구 초등학교",
    "kindergartens_yangcheon": "양천구 유치원",
    "major_parks_yangcheon": "양천구 공원",
    "obgyn_yangcheon": "양천구 산부인과",
    "pediatric_clinics_yangcheon": "양천구 소아청소년과",
    "playgrounds_yangcheon": "양천구 어린이놀이터",
    "safety_facilities_yangcheon": "양천구 안전시설",
    "subway_station_lines_capital_region": "수도권 지하철역",
}


def _normalise_record_id(value: object) -> str:
    result = str(value or "").strip()
    return result[4:] if result.startswith("row:") else result


def _normalise_name(value: object) -> str:
    return "".join(str(value or "").lower().split())


def _coordinate_key(row: Mapping[str, Any]) -> tuple[float, float]:
    return (round(float(row["latitude"]), 7), round(float(row["longitude"]), 7))


def _as_json(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _deduplicate_access(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse source-ID aliases that map to one remote physical facility."""
    selected: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (
            str(row["complex_id"]),
            str(row["feature_id"]),
            str(row["access_group"]),
            str(row["main_origin_id"]),
            str(row["calculation_version"]),
        )
        existing = selected.get(key)
        if existing is None:
            selected[key] = row
            continue
        rank = (
            row["access_status"] != "available",
            row["walk_time_min"] is None,
            float(row["walk_time_min"] or float("inf")),
            float(row["walk_distance_m"] or float("inf")),
        )
        existing_rank = (
            existing["access_status"] != "available",
            existing["walk_time_min"] is None,
            float(existing["walk_time_min"] or float("inf")),
            float(existing["walk_distance_m"] or float("inf")),
        )
        if rank < existing_rank:
            selected[key] = row
    return list(selected.values())


class SupabaseRest:
    def __init__(self) -> None:
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        self.base_url = settings.supabase_url.rstrip("/") + "/rest/v1/"
        self.headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
        }

    def fetch_all(self, table: str, select: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with httpx.Client(timeout=60) as client:
            for offset in range(0, 100_000, 1_000):
                response = client.get(
                    self.base_url + table,
                    params={"select": select, "limit": "1000", "offset": str(offset)},
                    headers=self.headers,
                )
                response.raise_for_status()
                batch = response.json()
                if not isinstance(batch, list):
                    raise RuntimeError(f"Unexpected {table} response")
                rows.extend(batch)
                if len(batch) < 1_000:
                    return rows
        raise RuntimeError(f"{table} exceeded the loader page limit")

    def upsert(self, table: str, rows: list[dict[str, Any]], conflict_columns: Iterable[str], batch_size: int) -> None:
        if not rows:
            return
        conflict = ",".join(conflict_columns)
        headers = {
            **self.headers,
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        }
        with httpx.Client(timeout=120) as client:
            for start in range(0, len(rows), batch_size):
                batch = rows[start : start + batch_size]
                response = client.post(
                    self.base_url + table,
                    params={"on_conflict": conflict},
                    headers=headers,
                    json=batch,
                )
                if response.status_code >= 400:
                    raise RuntimeError(
                        f"{table} batch {start // batch_size + 1} failed: "
                        f"{response.status_code} {response.text[:500]}"
                    )


@dataclass(frozen=True)
class FeatureMapper:
    remote_ids: set[str]
    by_source: Mapping[tuple[str, str], tuple[str, ...]]
    by_name_coordinate: Mapping[tuple[str, str, float, float], tuple[str, ...]]
    by_coordinate: Mapping[tuple[str, float, float], tuple[str, ...]]

    @classmethod
    def from_remote(cls, rows: Iterable[Mapping[str, Any]]) -> "FeatureMapper":
        remote_ids: set[str] = set()
        by_source: dict[tuple[str, str], list[str]] = defaultdict(list)
        by_name_coordinate: dict[tuple[str, str, float, float], list[str]] = defaultdict(list)
        by_coordinate: dict[tuple[str, float, float], list[str]] = defaultdict(list)
        for row in rows:
            feature_id = str(row["feature_id"])
            feature_type = str(row["feature_type"])
            latitude, longitude = _coordinate_key(row)
            remote_ids.add(feature_id)
            by_source[(feature_type, _normalise_record_id(row.get("source_record_id")))].append(feature_id)
            by_name_coordinate[(feature_type, _normalise_name(row.get("name")), latitude, longitude)].append(feature_id)
            by_coordinate[(feature_type, latitude, longitude)].append(feature_id)
        return cls(
            remote_ids=remote_ids,
            by_source={key: tuple(value) for key, value in by_source.items()},
            by_name_coordinate={key: tuple(value) for key, value in by_name_coordinate.items()},
            by_coordinate={key: tuple(value) for key, value in by_coordinate.items()},
        )

    def match(self, local: Mapping[str, Any]) -> tuple[str | None, str | None]:
        feature_id = str(local["feature_id"])
        if feature_id in self.remote_ids:
            return feature_id, "id"
        feature_type = str(local["feature_type"])
        latitude, longitude = _coordinate_key(local)
        candidates = self.by_source.get((feature_type, _normalise_record_id(local.get("source_record_id"))), ())
        if len(candidates) == 1:
            return candidates[0], "source_record"
        candidates = self.by_name_coordinate.get(
            (feature_type, _normalise_name(local.get("name")), latitude, longitude), ()
        )
        if len(candidates) == 1:
            return candidates[0], "name_coordinate"
        candidates = self.by_coordinate.get((feature_type, latitude, longitude), ())
        if len(candidates) == 1:
            return candidates[0], "coordinate"
        return None, None


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def _source_dataset(dataset_id: str, source_name: str, source_file: str) -> dict[str, Any]:
    return {
        "source_dataset_id": dataset_id,
        "source_name": source_name,
        "source_file": source_file,
        "source_sha256": None,
        "reference_date": "2026-08-11",
        "license_name": "source table provenance",
        "metadata": {"loader": "load_environment_serving_to_supabase"},
    }


def _transport_payloads(
    profile_rows: Iterable[Mapping[str, str]],
    remote_rows: Iterable[Mapping[str, Any]],
    transit_geojson: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    remote_ids = {str(row["feature_id"]) for row in remote_rows}
    buses_by_record = {
        _normalise_record_id(row.get("source_record_id")): str(row["feature_id"])
        for row in remote_rows
        if row.get("feature_type") == "bus_stop"
    }
    exits: dict[str, Mapping[str, Any]] = {}
    buses: dict[str, Mapping[str, Any]] = {}
    for feature in transit_geojson.get("features", []):
        properties = feature.get("properties", {})
        if properties.get("target_kind") == "subway":
            exits[str(properties.get("exit_id"))] = feature
        elif properties.get("target_kind") == "bus":
            buses[str(properties.get("target_id") or properties.get("stop_id"))] = feature

    source_datasets = [
        _source_dataset(SUBWAY_EXIT_DATASET_ID, "양천구 인접 지하철 출입구", "work/07_yangcheon_gu/02_accessibility/transit_stops.geojson"),
        _source_dataset(BOUNDARY_BUS_DATASET_ID, "양천구 경계 지원 버스정류장", "work/07_yangcheon_gu/02_accessibility/transit_stops.geojson"),
    ]
    new_features: dict[str, dict[str, Any]] = {}
    access_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for row in profile_rows:
        complex_id = offline.empty_to_none(row.get("complex_id"))
        origin_id = offline.empty_to_none(row.get("main_origin_id"))
        origin_method = offline.empty_to_none(row.get("origin_method"))
        if not all((complex_id, origin_id, origin_method)):
            raise ValueError("Transport profile is missing complex/origin identifiers")
        reference_date = offline.empty_to_none(row.get("access_reference_date"))
        qa_flags = offline.split_flags(row.get("qa_flags"))
        failure_reason = offline.empty_to_none(row.get("failure_reason"))

        exit_id = offline.empty_to_none(row.get("nearest_subway_exit"))
        subway_feature_id = f"subway_exit:{exit_id}" if exit_id else None
        if subway_feature_id and subway_feature_id not in remote_ids:
            source = exits.get(str(exit_id))
            if not source:
                raise ValueError(f"Missing GeoJSON record for nearest subway exit {exit_id}")
            properties = source["properties"]
            longitude, latitude = source["geometry"]["coordinates"][:2]
            station_name = str(properties.get("station_name") or "지하철")
            new_features[subway_feature_id] = {
                "feature_id": subway_feature_id,
                "source_dataset_id": SUBWAY_EXIT_DATASET_ID,
                "source_record_id": str(exit_id),
                "layer_category": "transit",
                "axis": "transport",
                "feature_type": "subway_exit",
                "parent_feature_id": None,
                "line_names": [str(properties["line"])] if properties.get("line") else [],
                "service_types": [],
                "name": f"{station_name} 출입구",
                "address": None,
                "scope_role": "boundary_support",
                "longitude": float(longitude),
                "latitude": float(latitude),
                "geometry": None,
                "coordinate_status": "verified_wgs84",
                "coordinate_method": "accessibility_input_wgs84",
                "record_status": "active",
                "map_visible": True,
                "reference_date": reference_date,
                "attributes": {
                    "stationName": station_name,
                    "lineName": properties.get("line"),
                    "stationCode": properties.get("station_code"),
                    "exitId": str(exit_id),
                },
                "qa_flags": [],
            }
            remote_ids.add(subway_feature_id)

        bus_stop_id = offline.empty_to_none(row.get("nearest_bus_stop_id"))
        bus_feature_id = buses_by_record.get(str(bus_stop_id)) if bus_stop_id else None
        if bus_stop_id and not bus_feature_id:
            bus_feature_id = f"bus_stop:{bus_stop_id}"
            if bus_feature_id not in remote_ids:
                source = buses.get(str(bus_stop_id))
                if not source:
                    raise ValueError(f"Missing GeoJSON record for nearest bus stop {bus_stop_id}")
                properties = source["properties"]
                longitude, latitude = source["geometry"]["coordinates"][:2]
                new_features[bus_feature_id] = {
                    "feature_id": bus_feature_id,
                    "source_dataset_id": BOUNDARY_BUS_DATASET_ID,
                    "source_record_id": str(bus_stop_id),
                    "layer_category": "transit",
                    "axis": "transport",
                    "feature_type": "bus_stop",
                    "parent_feature_id": None,
                    "line_names": [],
                    "service_types": [],
                    "name": properties.get("stop_name"),
                    "address": None,
                    "scope_role": "boundary_support",
                    "longitude": float(longitude),
                    "latitude": float(latitude),
                    "geometry": None,
                    "coordinate_status": "verified_wgs84",
                    "coordinate_method": "accessibility_input_wgs84",
                    "record_status": "active",
                    "map_visible": True,
                    "reference_date": reference_date,
                    "attributes": {"arsId": properties.get("ars_id"), "stopType": properties.get("stop_type")},
                    "qa_flags": [],
                }
                remote_ids.add(bus_feature_id)

        for group, feature_id, distance_key, time_key, straight_key, limit in (
            ("subway_exit", subway_feature_id, "subway_walk_distance_m", "subway_walk_time_min", "subway_straight_distance_m", None),
            ("bus_stop", bus_feature_id, "bus_stop_walk_distance_m", "bus_stop_walk_time_min", None, 500.0),
        ):
            if not feature_id:
                continue
            access_rows.append(
                {
                    "complex_id": complex_id,
                    "feature_id": feature_id,
                    "access_group": group,
                    "main_origin_id": origin_id,
                    "origin_method": origin_method,
                    "calculation_version": TRANSPORT_CALCULATION_VERSION,
                    "policy_version": TRANSPORT_POLICY_VERSION,
                    "reference_date": reference_date,
                    "straight_distance_m": offline.to_float(row.get(straight_key), f"transport.{straight_key}") if straight_key else None,
                    "walk_distance_m": offline.to_float(row.get(distance_key), f"transport.{distance_key}"),
                    "walk_time_min": offline.to_float(row.get(time_key), f"transport.{time_key}"),
                    "distance_method": "walking_network",
                    "access_status": "available",
                    "category_distance_limit_m": limit,
                    "is_nearest": True,
                    "selection_reason": "nearest",
                    "failure_reason": failure_reason,
                    "qa_flags": qa_flags,
                }
            )
            metrics: dict[str, Any]
            if group == "subway_exit":
                metrics = {
                    "stationName": offline.empty_to_none(row.get("nearest_subway_station")),
                    "lineName": offline.empty_to_none(row.get("nearest_subway_line")),
                    "exitId": exit_id,
                }
            else:
                metrics = {
                    "busStopCountWithin500WalkMeters": offline.to_int(row.get("bus_stop_count_500m"), "transport.bus_stop_count_500m"),
                    "stopName": offline.empty_to_none(row.get("nearest_bus_stop_name")),
                }
            summary_rows.append(
                {
                    "complex_id": complex_id,
                    "access_group": group,
                    "main_origin_id": origin_id,
                    "origin_method": origin_method,
                    "calculation_version": TRANSPORT_CALCULATION_VERSION,
                    "policy_version": TRANSPORT_POLICY_VERSION,
                    "reference_date": reference_date,
                    "category_distance_limit_m": limit,
                    "nearest_feature_id": feature_id,
                    "nearest_walk_distance_m": offline.to_float(row.get(distance_key), f"transport.{distance_key}"),
                    "nearest_walk_time_min": offline.to_float(row.get(time_key), f"transport.{time_key}"),
                    "count_within_5min": 0,
                    "count_within_10min": 0,
                    "count_within_15min": 0,
                    "selected_feature_count": 1,
                    "metrics": metrics,
                    "summary_status": "available",
                    "failure_reason": failure_reason,
                    "qa_flags": qa_flags,
                }
            )
    return source_datasets, list(new_features.values()), access_rows, summary_rows


def _build_payloads(rest: SupabaseRest, workspace_root: Path) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    source_paths = {
        "profile": workspace_root / "work/07_yangcheon_gu/05_integration/complex_transport_profile.csv",
        "features": workspace_root / "data/processed/environment/pois/environment_features.csv",
        "access": workspace_root / "data/processed/environment/complex_environment_access.csv",
        "summary": workspace_root / "data/processed/environment/complex_environment_summary.csv",
        "transit": workspace_root / "work/07_yangcheon_gu/02_accessibility/transit_stops.geojson",
    }
    missing = [str(path) for path in source_paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("Required local inputs are missing: " + ", ".join(missing))

    remote_features = rest.fetch_all(
        "environment_feature", "feature_id,feature_type,source_record_id,name,latitude,longitude"
    )
    remote_datasets = rest.fetch_all(
        "source_dataset", "source_dataset_id,source_name,source_file,source_sha256,reference_date,license_name,metadata"
    )
    mapper = FeatureMapper.from_remote(remote_features)
    local_features = {row["feature_id"]: row for row in _read_csv(source_paths["features"])}
    typed_access = offline.build_environment_access(_read_csv(source_paths["access"]))
    typed_summary = offline.build_environment_summaries(_read_csv(source_paths["summary"]))
    profile_rows = _read_csv(source_paths["profile"])

    mapped_access: list[dict[str, Any]] = []
    mapping_methods: Counter[str] = Counter()
    unmapped_features: set[str] = set()
    for row in typed_access:
        if row["access_group"] not in PRECOMPUTED_GROUPS:
            continue
        feature = local_features.get(row["feature_id"])
        if not feature:
            unmapped_features.add(row["feature_id"])
            continue
        mapped_id, method = mapper.match(feature)
        if not mapped_id:
            unmapped_features.add(row["feature_id"])
            continue
        mapping_methods[method or "unknown"] += 1
        mapped_access.append({**row, "feature_id": mapped_id})

    mapped_access = _deduplicate_access(mapped_access)
    access_by_group: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in mapped_access:
        access_by_group[(str(row["complex_id"]), str(row["access_group"]))].append(row)
    mapped_summaries: list[dict[str, Any]] = []
    for template in typed_summary:
        group = str(template["access_group"])
        if group not in PRECOMPUTED_GROUPS:
            continue
        rows = access_by_group[(str(template["complex_id"]), group)]
        available = [row for row in rows if row["access_status"] == "available" and row["walk_time_min"] is not None]
        nearest = min(
            available,
            key=lambda row: (float(row["walk_time_min"]), float(row["walk_distance_m"] or float("inf")), str(row["feature_id"])),
            default=None,
        )
        raw_status = str(template["summary_status"])
        status = "available" if nearest else raw_status
        mapped_summaries.append(
            {
                **template,
                "nearest_feature_id": nearest["feature_id"] if nearest else None,
                "nearest_walk_distance_m": nearest["walk_distance_m"] if nearest else None,
                "nearest_walk_time_min": nearest["walk_time_min"] if nearest else None,
                "count_within_5min": sum(float(row["walk_time_min"]) <= 5 for row in available),
                "count_within_10min": sum(float(row["walk_time_min"]) <= 10 for row in available),
                "count_within_15min": sum(float(row["walk_time_min"]) <= 15 for row in available),
                "selected_feature_count": len(available),
                "metrics": _as_json(template["metrics"]),
                "summary_status": status,
                "failure_reason": template["failure_reason"] if nearest is None else None,
            }
        )

    transport_sources, transport_features, transport_access, transport_summaries = _transport_payloads(
        profile_rows,
        remote_features,
        json.loads(source_paths["transit"].read_text(encoding="utf-8-sig")),
    )
    corrected_datasets = [
        {**row, "source_name": SOURCE_NAME_OVERRIDES.get(str(row["source_dataset_id"]), row["source_name"])}
        for row in remote_datasets
    ]
    datasets_by_id = {str(row["source_dataset_id"]): row for row in corrected_datasets}
    datasets_by_id.update({str(row["source_dataset_id"]): row for row in transport_sources})
    payloads = {
        "source_dataset": list(datasets_by_id.values()),
        "apartment_complex": offline.build_complexes(profile_rows),
        "environment_feature": transport_features,
        "complex_feature_access": _deduplicate_access([*mapped_access, *transport_access]),
        "complex_environment_summary": [*mapped_summaries, *transport_summaries],
    }
    qa = {
        "status": "READY_TO_APPLY",
        "counts": {name: len(rows) for name, rows in payloads.items()},
        "remote_environment_feature_count": len(remote_features),
        "access_mapping_methods": dict(sorted(mapping_methods.items())),
        "unmapped_local_feature_count": len(unmapped_features),
        "unmapped_local_feature_samples": sorted(unmapped_features)[:20],
    }
    return payloads, qa


def _apply(rest: SupabaseRest, payloads: Mapping[str, list[dict[str, Any]]], batch_size: int) -> None:
    rest.upsert("source_dataset", payloads["source_dataset"], ("source_dataset_id",), batch_size)
    rest.upsert("environment_feature", payloads["environment_feature"], ("feature_id",), batch_size)
    rest.upsert("apartment_complex", payloads["apartment_complex"], ("complex_id",), batch_size)
    rest.upsert(
        "complex_feature_access",
        payloads["complex_feature_access"],
        ("complex_id", "feature_id", "access_group", "main_origin_id", "calculation_version"),
        batch_size,
    )
    rest.upsert(
        "complex_environment_summary",
        payloads["complex_environment_summary"],
        ("complex_id", "access_group", "calculation_version"),
        batch_size,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Load five-table environment serving data to Supabase")
    parser.add_argument("--workspace-root", type=Path, default=WORKSPACE_ROOT)
    parser.add_argument("--apply", action="store_true", help="Perform Supabase upserts after validation")
    parser.add_argument(
        "--source-metadata-only",
        action="store_true",
        help="Apply only source_dataset metadata corrections (requires --apply)",
    )
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 1_000:
        raise ValueError("batch-size must be between 1 and 1000")
    if args.source_metadata_only and not args.apply:
        raise ValueError("--source-metadata-only requires --apply")
    rest = SupabaseRest()
    payloads, qa = _build_payloads(rest, args.workspace_root.resolve())
    if args.apply:
        if args.source_metadata_only:
            rest.upsert("source_dataset", payloads["source_dataset"], ("source_dataset_id",), args.batch_size)
        else:
            _apply(rest, payloads, args.batch_size)
        qa["status"] = "APPLIED"
    print(json.dumps(qa, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, RuntimeError, ValueError, httpx.HTTPError) as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)
