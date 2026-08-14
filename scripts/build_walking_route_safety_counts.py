"""Attach 20 m route-line safety counts to local stored-route GeoJSON exports.

The output only adds compact counts to route properties. It does not duplicate
the individual crosswalk, signal, or CCTV geometries in the route table.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo


EARTH_RADIUS_M = 6_371_000.0
SAFETY_CALCULATION_VERSION = "route_safety_point_to_linestring_20m_v1"
DEFAULT_THRESHOLD_M = 20
DEFAULT_GRID_DEGREES = 0.002


class SafetyInputError(ValueError):
    """Raised when a local route or safety-point export is unsafe to process."""


def load_feature_collection(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SafetyInputError(f"Cannot read route GeoJSON: {path}") from exc
    if payload.get("type") != "FeatureCollection" or not isinstance(payload.get("features"), list):
        raise SafetyInputError(f"Route GeoJSON must be a FeatureCollection: {path}")
    return payload


def load_safety_points(path: Path) -> dict[str, list[tuple[str, float, float]]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SafetyInputError(f"Cannot read safety point JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise SafetyInputError("Safety point JSON must be an object keyed by safety category.")
    expected = {"crosswalk", "signal", "cctv"}
    points: dict[str, list[tuple[str, float, float]]] = {}
    for category in expected:
        source = payload.get(category)
        if not isinstance(source, list):
            raise SafetyInputError(f"Safety point JSON must include a {category} list.")
        parsed: list[tuple[str, float, float]] = []
        for index, point in enumerate(source):
            if not isinstance(point, dict):
                raise SafetyInputError(f"{category} point {index}: object expected.")
            identifier = str(point.get("id") or "").strip()
            try:
                longitude = float(point["longitude"])
                latitude = float(point["latitude"])
            except (KeyError, TypeError, ValueError) as exc:
                raise SafetyInputError(f"{category} point {index}: valid longitude and latitude required.") from exc
            if not identifier or not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
                raise SafetyInputError(f"{category} point {index}: invalid ID or coordinate.")
            parsed.append((identifier, longitude, latitude))
        points[category] = parsed
    return points


def grid_cell(longitude: float, latitude: float, grid_degrees: float) -> tuple[int, int]:
    return math.floor(longitude / grid_degrees), math.floor(latitude / grid_degrees)


def point_to_segment_meters(
    point_longitude: float,
    point_latitude: float,
    start: list[float],
    end: list[float],
) -> float:
    """Locally projected point-to-segment distance; sufficient for a 20 m threshold."""
    longitude_scale = math.pi / 180 * EARTH_RADIUS_M * math.cos(math.radians(point_latitude))
    latitude_scale = math.pi / 180 * EARTH_RADIUS_M
    start_x = (float(start[0]) - point_longitude) * longitude_scale
    start_y = (float(start[1]) - point_latitude) * latitude_scale
    end_x = (float(end[0]) - point_longitude) * longitude_scale
    end_y = (float(end[1]) - point_latitude) * latitude_scale
    delta_x = end_x - start_x
    delta_y = end_y - start_y
    if delta_x == 0 and delta_y == 0:
        return math.hypot(start_x, start_y)
    # The point is the local origin; project the vector from the start of the
    # segment to that origin onto the segment direction.
    ratio = max(0.0, min(1.0, -(start_x * delta_x + start_y * delta_y) / (delta_x * delta_x + delta_y * delta_y)))
    return math.hypot(start_x + ratio * delta_x, start_y + ratio * delta_y)


def is_on_route_within_threshold(
    longitude: float,
    latitude: float,
    coordinates: list[list[float]],
    threshold_m: float,
) -> bool:
    return any(
        point_to_segment_meters(longitude, latitude, start, end) <= threshold_m
        for start, end in zip(coordinates, coordinates[1:])
    )


def indexed_points(
    points: dict[str, list[tuple[str, float, float]]],
    grid_degrees: float,
) -> dict[str, dict[tuple[int, int], list[tuple[str, float, float]]]]:
    result: dict[str, dict[tuple[int, int], list[tuple[str, float, float]]]] = {}
    for category, values in points.items():
        index: dict[tuple[int, int], list[tuple[str, float, float]]] = defaultdict(list)
        for point in values:
            index[grid_cell(point[1], point[2], grid_degrees)].append(point)
        result[category] = index
    return result


def candidate_cells(
    coordinates: list[list[float]],
    *,
    threshold_m: float,
    grid_degrees: float,
) -> Iterable[tuple[int, int]]:
    min_longitude = min(point[0] for point in coordinates)
    max_longitude = max(point[0] for point in coordinates)
    min_latitude = min(point[1] for point in coordinates)
    max_latitude = max(point[1] for point in coordinates)
    latitude_padding = threshold_m / 111_320
    longitude_padding = latitude_padding / max(0.1, math.cos(math.radians((min_latitude + max_latitude) / 2)))
    start_x, start_y = grid_cell(min_longitude - longitude_padding, min_latitude - latitude_padding, grid_degrees)
    end_x, end_y = grid_cell(max_longitude + longitude_padding, max_latitude + latitude_padding, grid_degrees)
    # A route may sit against a grid-cell boundary. Include the immediately
    # adjacent cells so a point inside the geographic 20 m padded box is
    # never skipped because of floor rounding.
    for longitude_cell in range(start_x - 1, end_x + 2):
        for latitude_cell in range(start_y - 1, end_y + 2):
            yield longitude_cell, latitude_cell


def count_safety_points(
    coordinates: list[list[float]],
    index: dict[str, dict[tuple[int, int], list[tuple[str, float, float]]]],
    *,
    threshold_m: float,
    grid_degrees: float,
) -> dict[str, int]:
    cells = tuple(candidate_cells(coordinates, threshold_m=threshold_m, grid_degrees=grid_degrees))
    counts: dict[str, int] = {}
    for category, point_index in index.items():
        seen_ids: set[str] = set()
        count = 0
        for cell in cells:
            for identifier, longitude, latitude in point_index.get(cell, []):
                if identifier in seen_ids:
                    continue
                seen_ids.add(identifier)
                if is_on_route_within_threshold(longitude, latitude, coordinates, threshold_m):
                    count += 1
        counts[category] = count
    return counts


def attach_counts(
    collection: dict[str, Any],
    point_index: dict[str, dict[tuple[int, int], list[tuple[str, float, float]]]],
    *,
    threshold_m: int,
    calculated_at: str,
    grid_degrees: float = DEFAULT_GRID_DEGREES,
) -> dict[str, int]:
    totals = {"crosswalk": 0, "signal": 0, "cctv": 0}
    for feature_index, feature in enumerate(collection["features"]):
        geometry = feature.get("geometry")
        properties = feature.get("properties")
        coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
        if not isinstance(properties, dict) or geometry.get("type") != "LineString" or not isinstance(coordinates, list) or len(coordinates) < 2:
            raise SafetyInputError(f"Route feature {feature_index}: valid LineString and properties are required.")
        normalized_coordinates = [[float(coordinate[0]), float(coordinate[1])] for coordinate in coordinates]
        counts = count_safety_points(
            normalized_coordinates,
            point_index,
            threshold_m=threshold_m,
            grid_degrees=grid_degrees,
        )
        properties.update({
            "safety_match_threshold_m": threshold_m,
            "crosswalk_count": counts["crosswalk"],
            "pedestrian_signal_count": counts["signal"],
            "cctv_location_count": counts["cctv"],
            "safety_calculation_version": SAFETY_CALCULATION_VERSION,
            "safety_calculated_at": calculated_at,
        })
        for category, count in counts.items():
            totals[category] += count
    return totals


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pre-compute 20 m safety counts for stored walking-route GeoJSON.")
    parser.add_argument("--input", type=Path, action="append", required=True, help="Route GeoJSON; repeat for each input export.")
    parser.add_argument("--safety-points", type=Path, required=True, help="Local JSON containing crosswalk, signal, and CCTV point coordinates.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--threshold-m", type=int, default=DEFAULT_THRESHOLD_M)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.threshold_m <= 0:
        raise SafetyInputError("threshold-m must be positive.")
    points = load_safety_points(args.safety_points)
    point_index = indexed_points(points, DEFAULT_GRID_DEGREES)
    calculated_at = datetime.now(ZoneInfo("Asia/Seoul")).isoformat()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result = []
    for input_path in args.input:
        collection = load_feature_collection(input_path)
        totals = attach_counts(collection, point_index, threshold_m=args.threshold_m, calculated_at=calculated_at)
        output_path = args.output_dir / input_path.name
        output_path.write_text(json.dumps(collection, ensure_ascii=False), encoding="utf-8")
        source_metadata = input_path.with_name(input_path.stem + "_metadata.json")
        output_metadata = output_path.with_name(output_path.stem + "_metadata.json")
        if source_metadata.is_file():
            metadata = json.loads(source_metadata.read_text(encoding="utf-8"))
            metadata["route_safety_counts"] = {
                "threshold_m": args.threshold_m,
                "calculation_version": SAFETY_CALCULATION_VERSION,
                "calculated_at": calculated_at,
                "safety_point_counts": totals,
            }
            output_metadata.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
        result.append({"input": str(input_path), "output": str(output_path), "routeCount": len(collection["features"]), "safetyPointCounts": totals})
    print(json.dumps({"thresholdMeters": args.threshold_m, "calculatedAt": calculated_at, "outputs": result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
