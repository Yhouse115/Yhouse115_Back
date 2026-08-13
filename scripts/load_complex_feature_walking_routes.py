"""Validate and optionally upsert locally generated walking-route GeoJSON.

The default command is intentionally a dry run. Passing ``--apply`` is the
explicit opt-in that writes rows through Supabase's service-role REST API.
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

SUPPORTED_ACCESS_GROUPS = {"elementary_school", "childcare", "kindergarten", "park", "medical_clinic"}
DEFAULT_CALCULATION_VERSION = "oa21208_yangcheon_guro_extended_20260811_center_v2"
DEFAULT_MAIN_ORIGIN_ID = "complex_center"
DEFAULT_MAX_STORED_WALK_DISTANCE_M = 1500.0
UPSERT_COLUMNS = (
    "complex_id,feature_id,access_group,main_origin_id,calculation_version"
)


class RouteInputError(ValueError):
    """Raised when a local GeoJSON export cannot safely be loaded."""


def parse_coordinates(value: Any, *, feature_index: int) -> list[list[float]]:
    if not isinstance(value, list) or len(value) < 2:
        raise RouteInputError(f"Feature {feature_index}: LineString needs at least two coordinates.")
    coordinates: list[list[float]] = []
    for coordinate in value:
        if not isinstance(coordinate, list) or len(coordinate) != 2:
            raise RouteInputError(f"Feature {feature_index}: invalid route coordinate.")
        longitude, latitude = float(coordinate[0]), float(coordinate[1])
        if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
            raise RouteInputError(f"Feature {feature_index}: coordinate outside longitude/latitude bounds.")
        coordinates.append([longitude, latitude])
    return coordinates


def parse_qa_flags(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [flag for flag in value.split("/") if flag]
    if isinstance(value, list) and all(isinstance(flag, str) for flag in value):
        return [flag for flag in value if flag]
    raise RouteInputError("qa_flags must be a slash-delimited string or string array.")


def parse_optional_nonnegative_int(value: Any, *, field: str, feature_index: int) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise RouteInputError(f"Feature {feature_index}: {field} must be a non-negative integer.") from exc
    if parsed < 0:
        raise RouteInputError(f"Feature {feature_index}: {field} must be a non-negative integer.")
    return parsed


def parse_calculated_at(value: str) -> str:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except ValueError as exc:
        raise RouteInputError("calculated_at must be an ISO-8601 timestamp.") from exc


def parse_route_crossing_events(value: Any, *, feature_index: int) -> list[dict[str, Any]] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise RouteInputError(f"Feature {feature_index}: route_crossing_events must be an array.")
    events: list[dict[str, Any]] = []
    seen_link_ids: set[str] = set()
    seen_signal_ids: set[str] = set()
    for event_index, event in enumerate(value):
        if not isinstance(event, Mapping):
            raise RouteInputError(f"Feature {feature_index}: route_crossing_events[{event_index}] must be an object.")
        event_id = str(event.get("crosswalk_event_id") or "").strip()
        try:
            longitude = float(event["longitude"])
            latitude = float(event["latitude"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RouteInputError(f"Feature {feature_index}: crossing event coordinate is invalid.") from exc
        signals_value = event.get("pedestrian_signals", [])
        if not event_id or event_id in seen_link_ids or not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
            raise RouteInputError(f"Feature {feature_index}: crossing event is invalid or duplicated.")
        if not isinstance(signals_value, list):
            raise RouteInputError(f"Feature {feature_index}: pedestrian_signals must be an array.")
        signals: list[dict[str, Any]] = []
        signal_ids: list[str] = []
        for signal_index, signal in enumerate(signals_value):
            if not isinstance(signal, Mapping):
                raise RouteInputError(f"Feature {feature_index}: crossing-event signal {signal_index} must be an object.")
            signal_id = str(signal.get("id") or "").strip()
            try:
                signal_longitude = float(signal["longitude"])
                signal_latitude = float(signal["latitude"])
            except (KeyError, TypeError, ValueError) as exc:
                raise RouteInputError(f"Feature {feature_index}: crossing-event signal coordinate is invalid.") from exc
            if not signal_id or not -180 <= signal_longitude <= 180 or not -90 <= signal_latitude <= 90:
                raise RouteInputError(f"Feature {feature_index}: crossing-event signal is invalid.")
            signal_ids.append(signal_id)
            signals.append({"id": signal_id, "longitude": signal_longitude, "latitude": signal_latitude})
        if len(signal_ids) != len(set(signal_ids)):
            raise RouteInputError(f"Feature {feature_index}: crossing event signal IDs must be unique.")
        if seen_signal_ids.intersection(signal_ids):
            raise RouteInputError(f"Feature {feature_index}: a pedestrian signal can belong to only one crossing event.")
        seen_link_ids.add(event_id)
        seen_signal_ids.update(signal_ids)
        events.append({
            "crosswalk_event_id": event_id,
            "longitude": longitude,
            "latitude": latitude,
            "pedestrian_signals": signals,
        })
    return events


def load_json_object(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RouteInputError(f"Cannot read JSON input: {path}") from exc
    if not isinstance(value, dict):
        raise RouteInputError(f"JSON object expected: {path}")
    return value


def route_rows_from_geojson(
    geojson_path: Path,
    *,
    calculation_version: str,
    calculated_at: str,
    main_origin_id: str = DEFAULT_MAIN_ORIGIN_ID,
    max_stored_walk_distance_m: float = DEFAULT_MAX_STORED_WALK_DISTANCE_M,
) -> list[dict[str, Any]]:
    collection = load_json_object(geojson_path)
    features = collection.get("features")
    if collection.get("type") != "FeatureCollection" or not isinstance(features, list):
        raise RouteInputError("Input must be a GeoJSON FeatureCollection.")

    rows: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str, str, str]] = set()
    for index, feature in enumerate(features):
        if not isinstance(feature, dict):
            raise RouteInputError(f"Feature {index}: object expected.")
        properties = feature.get("properties")
        geometry = feature.get("geometry")
        if not isinstance(properties, dict) or not isinstance(geometry, dict):
            raise RouteInputError(f"Feature {index}: properties and geometry are required.")
        access_group = str(properties.get("access_group") or properties.get("feature_type") or "").strip()
        if access_group not in SUPPORTED_ACCESS_GROUPS:
            raise RouteInputError(
                f"Feature {index}: access_group must be one of {', '.join(sorted(SUPPORTED_ACCESS_GROUPS))}."
            )
        if geometry.get("type") != "LineString":
            raise RouteInputError(f"Feature {index}: geometry must be a LineString.")

        complex_id = str(properties.get("complex_id") or "").strip()
        feature_id = str(properties.get("feature_id") or properties.get("school_feature_id") or "").strip()
        route_method = str(properties.get("route_method") or "").strip()
        if not complex_id or not feature_id or not route_method:
            raise RouteInputError(f"Feature {index}: complex_id, feature_id, and route_method are required.")
        try:
            walk_distance_m = float(properties["walk_distance_m"])
            walk_time_min = float(properties["walk_time_min"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RouteInputError(f"Feature {index}: valid walking distance and time are required.") from exc
        if not 0 <= walk_distance_m < max_stored_walk_distance_m or walk_time_min < 0:
            raise RouteInputError(
                f"Feature {index}: only non-negative routes below {max_stored_walk_distance_m:g} m may be loaded."
            )

        row_main_origin_id = str(properties.get("main_origin_id") or properties.get("origin_method") or main_origin_id)
        key = (complex_id, feature_id, access_group, row_main_origin_id, calculation_version)
        if key in seen_keys:
            raise RouteInputError(f"Feature {index}: duplicate route key {key!r}.")
        seen_keys.add(key)
        crossing_events = parse_route_crossing_events(properties.get("route_crossing_events"), feature_index=index)
        crosswalk_count = parse_optional_nonnegative_int(
            properties.get("crosswalk_count"), field="crosswalk_count", feature_index=index
        )
        pedestrian_signal_count = parse_optional_nonnegative_int(
            properties.get("pedestrian_signal_count"), field="pedestrian_signal_count", feature_index=index
        )
        if crossing_events is not None:
            event_signal_count = sum(len(event["pedestrian_signals"]) for event in crossing_events)
            if crosswalk_count != len(crossing_events) or pedestrian_signal_count != event_signal_count:
                raise RouteInputError(
                    f"Feature {index}: crossing-event counts must equal crosswalk_count and pedestrian_signal_count."
                )
        rows.append(
            {
                "complex_id": complex_id,
                "feature_id": feature_id,
                "access_group": access_group,
                "main_origin_id": row_main_origin_id,
                "calculation_version": calculation_version,
                "route_coordinates": parse_coordinates(geometry.get("coordinates"), feature_index=index),
                "walk_distance_m": walk_distance_m,
                "walk_time_min": walk_time_min,
                "route_method": route_method,
                "calculated_at": calculated_at,
                "route_metadata": {
                    "originMethod": properties.get("origin_method"),
                    "graphDistanceMeters": properties.get("graph_distance_m"),
                    "originSnapDistanceMeters": properties.get("origin_snap_distance_m"),
                    "destinationSnapDistanceMeters": properties.get("destination_snap_distance_m"),
                    "accessDistanceDeltaMeters": properties.get("access_distance_delta_m"),
                },
                "qa_flags": parse_qa_flags(properties.get("qa_flags")),
                "safety_match_threshold_m": parse_optional_nonnegative_int(
                    properties.get("safety_match_threshold_m"),
                    field="safety_match_threshold_m",
                    feature_index=index,
                ),
                "crosswalk_count": crosswalk_count,
                "pedestrian_signal_count": pedestrian_signal_count,
                "cctv_location_count": parse_optional_nonnegative_int(
                    properties.get("cctv_location_count"), field="cctv_location_count", feature_index=index
                ),
                "route_crossing_events": crossing_events,
                "safety_calculation_version": properties.get("safety_calculation_version") or None,
                "safety_calculated_at": (
                    parse_calculated_at(str(properties["safety_calculated_at"]))
                    if properties.get("safety_calculated_at")
                    else None
                ),
            }
        )
    if not rows:
        raise RouteInputError("Input contains no routes.")
    return rows


def chunks(values: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for offset in range(0, len(values), size):
        yield values[offset : offset + size]


def configured_value(name: str) -> str:
    """Read a loader setting without requiring the application virtualenv."""
    value = os.environ.get(name, "").strip()
    if value:
        return value
    environment_path = Path(__file__).resolve().parents[1] / ".env"
    if not environment_path.is_file():
        return ""
    for line in environment_path.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, candidate = line.split("=", 1)
        if key.strip().removeprefix("export ").strip() == name:
            return candidate.strip().strip('"').strip("'")
    return ""


def upsert_rows(rows: list[dict[str, Any]], *, batch_size: int) -> None:
    # Keep validation-only runs independent from the backend virtualenv. The
    # configured Supabase client is only necessary once a caller explicitly
    # requests a write with --apply.
    from urllib.error import HTTPError, URLError
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen

    supabase_url = configured_value("SUPABASE_URL")
    service_role_key = configured_value("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required with --apply.")
    url = supabase_url.rstrip("/") + "/rest/v1/complex_feature_walking_route"
    headers = {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    request_url = f"{url}?{urlencode({'on_conflict': UPSERT_COLUMNS})}"
    for batch in chunks(rows, batch_size):
        request = Request(
            request_url,
            data=json.dumps(batch, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=60) as response:
                if not 200 <= response.status < 300:
                    raise RuntimeError(f"Supabase route upsert failed with HTTP {response.status}.")
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"Supabase route upsert failed with HTTP {exc.code}: {details}") from exc
        except URLError as exc:
            raise RuntimeError("Supabase route upsert could not reach the configured project.") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load pre-computed complex-to-facility walking route GeoJSON.")
    parser.add_argument("--input", type=Path, required=True, help="Path to a local walking-route GeoJSON export")
    parser.add_argument(
        "--metadata",
        type=Path,
        help="Path to the matching route metadata JSON (defaults to the input sidecar name).",
    )
    parser.add_argument("--calculation-version", default=DEFAULT_CALCULATION_VERSION)
    parser.add_argument("--calculated-at", help="ISO-8601 timestamp; defaults to metadata.executed_at.")
    parser.add_argument("--main-origin-id", default=DEFAULT_MAIN_ORIGIN_ID)
    parser.add_argument(
        "--max-stored-walk-distance-m",
        type=float,
        default=DEFAULT_MAX_STORED_WALK_DISTANCE_M,
        help="Reject route rows at or beyond this walk distance (default: 1500 m).",
    )
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--apply", action="store_true", help="Write to Supabase. Omit for validation-only dry run.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.batch_size < 1 or args.batch_size > 1_000:
        raise RouteInputError("batch_size must be between 1 and 1000.")
    if args.max_stored_walk_distance_m <= 0:
        raise RouteInputError("max-stored-walk-distance-m must be positive.")
    metadata_path = args.metadata or args.input.with_name(args.input.stem + "_metadata.json")
    metadata = load_json_object(metadata_path)
    calculated_at = parse_calculated_at(args.calculated_at or str(metadata.get("executed_at") or ""))
    rows = route_rows_from_geojson(
        args.input,
        calculation_version=args.calculation_version,
        calculated_at=calculated_at,
        main_origin_id=args.main_origin_id,
        max_stored_walk_distance_m=args.max_stored_walk_distance_m,
    )
    if args.apply:
        upsert_rows(rows, batch_size=args.batch_size)
    print(
        json.dumps(
            {
                "status": "APPLIED" if args.apply else "DRY_RUN",
                "rowCount": len(rows),
                "calculationVersion": args.calculation_version,
                "calculatedAt": calculated_at,
                "input": str(args.input),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
