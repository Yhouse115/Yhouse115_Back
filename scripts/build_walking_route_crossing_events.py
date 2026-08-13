"""Recompute route safety using actual OA-21208 crosswalk links.

Unlike the older point-to-route proximity batch, this tool recognises a
crosswalk only when a segment of the stored route is an OA-21208 link whose
``crosswalk`` flag is enabled.  A pedestrian signal is retained only when it
is close to one of those selected crossing links.  This keeps route panels
and route-only map markers about crossings the user actually makes.

The tool is intentionally local and batch-only.  It never writes Supabase.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from build_walking_route_safety_counts import (
    DEFAULT_GRID_DEGREES,
    SafetyInputError,
    candidate_cells,
    indexed_points,
    load_feature_collection,
    load_safety_points,
    point_to_segment_meters,
)


CALCULATION_VERSION = "route_crossing_link_and_signal_20m_v1"
DEFAULT_SIGNAL_MATCH_THRESHOLD_M = 20
COORDINATE_DECIMALS = 7


@dataclass(frozen=True)
class CrosswalkLink:
    link_id: str
    coordinates: tuple[tuple[float, float], ...]

    @property
    def midpoint(self) -> tuple[float, float]:
        first = self.coordinates[0]
        last = self.coordinates[-1]
        return ((first[0] + last[0]) / 2, (first[1] + last[1]) / 2)


def rounded_coordinate(value: Any) -> tuple[float, float]:
    try:
        longitude, latitude = float(value[0]), float(value[1])
    except (IndexError, TypeError, ValueError) as exc:
        raise SafetyInputError("Walking-link geometry contains an invalid coordinate.") from exc
    if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
        raise SafetyInputError("Walking-link geometry contains an out-of-range coordinate.")
    return round(longitude, COORDINATE_DECIMALS), round(latitude, COORDINATE_DECIMALS)


def segment_key(start: tuple[float, float], end: tuple[float, float]) -> tuple[tuple[float, float], tuple[float, float]]:
    """Use an undirected key because the walking graph may traverse either way."""
    return (start, end) if start <= end else (end, start)


def is_truthy(value: Any) -> bool:
    return str(value).strip().casefold() in {"1", "true", "t", "y", "yes"}


def load_crosswalk_link_index(
    path: Path,
) -> tuple[dict[str, CrosswalkLink], dict[tuple[tuple[float, float], tuple[float, float]], set[str]]]:
    collection = load_feature_collection(path)
    links: dict[str, CrosswalkLink] = {}
    segment_index: dict[tuple[tuple[float, float], tuple[float, float]], set[str]] = defaultdict(set)
    for feature_index, feature in enumerate(collection["features"]):
        properties = feature.get("properties")
        geometry = feature.get("geometry")
        if not isinstance(properties, dict) or not isinstance(geometry, dict):
            continue
        if not is_truthy(properties.get("crosswalk")):
            continue
        link_id = str(properties.get("link_id") or "").strip()
        coordinates = geometry.get("coordinates")
        if not link_id or geometry.get("type") != "LineString" or not isinstance(coordinates, list) or len(coordinates) < 2:
            raise SafetyInputError(f"Crosswalk link {feature_index}: ID and LineString geometry are required.")
        normalized = tuple(rounded_coordinate(coordinate) for coordinate in coordinates)
        link = CrosswalkLink(link_id=link_id, coordinates=normalized)
        existing = links.get(link_id)
        if existing and existing != link:
            raise SafetyInputError(f"Crosswalk link ID is duplicated with different geometry: {link_id}")
        links[link_id] = link
        for start, end in zip(normalized, normalized[1:]):
            segment_index[segment_key(start, end)].add(link_id)
    if not links:
        raise SafetyInputError(f"No crosswalk=1 links were found: {path}")
    return links, segment_index


def selected_crosswalk_links(
    route_coordinates: list[list[float]],
    segment_index: dict[tuple[tuple[float, float], tuple[float, float]], set[str]],
) -> set[str]:
    normalized = [rounded_coordinate(coordinate) for coordinate in route_coordinates]
    selected: set[str] = set()
    for start, end in zip(normalized, normalized[1:]):
        selected.update(segment_index.get(segment_key(start, end), ()))
    return selected


def distance_to_link_meters(longitude: float, latitude: float, link: CrosswalkLink) -> float:
    return min(
        point_to_segment_meters(longitude, latitude, list(start), list(end))
        for start, end in zip(link.coordinates, link.coordinates[1:])
    )


def selected_signal_ids(
    route_coordinates: list[list[float]],
    selected_links: Iterable[CrosswalkLink],
    signal_index: dict[tuple[int, int], list[tuple[str, float, float]]],
    *,
    threshold_m: float,
) -> list[str]:
    """Return signals located at a crossing link used by the selected route."""
    links = tuple(selected_links)
    if not links:
        return []
    candidates: dict[str, tuple[float, float]] = {}
    for cell in candidate_cells(route_coordinates, threshold_m=threshold_m, grid_degrees=DEFAULT_GRID_DEGREES):
        for identifier, longitude, latitude in signal_index.get(cell, []):
            candidates.setdefault(identifier, (longitude, latitude))
    return sorted(
        identifier
        for identifier, (longitude, latitude) in candidates.items()
        if any(distance_to_link_meters(longitude, latitude, link) <= threshold_m for link in links)
    )


def attach_crossing_events(
    collection: dict[str, Any],
    *,
    links: dict[str, CrosswalkLink],
    crosswalk_segment_index: dict[tuple[tuple[float, float], tuple[float, float]], set[str]],
    safety_points: dict[str, list[tuple[str, float, float]]],
    signal_match_threshold_m: int,
    calculated_at: str,
) -> dict[str, int]:
    """Replace crosswalk/signal proximity counts with true crossing events."""
    safety_index = indexed_points(safety_points, DEFAULT_GRID_DEGREES)
    signal_points_by_id = {identifier: (longitude, latitude) for identifier, longitude, latitude in safety_points["signal"]}
    totals = {"crosswalk": 0, "signal": 0, "cctv": 0}
    for feature_index, feature in enumerate(collection["features"]):
        geometry = feature.get("geometry")
        properties = feature.get("properties")
        coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
        if not isinstance(properties, dict) or not isinstance(geometry, dict) or geometry.get("type") != "LineString" or not isinstance(coordinates, list) or len(coordinates) < 2:
            raise SafetyInputError(f"Route feature {feature_index}: valid LineString and properties are required.")
        route_coordinates = [[float(coordinate[0]), float(coordinate[1])] for coordinate in coordinates]
        crossing_ids = sorted(selected_crosswalk_links(route_coordinates, crosswalk_segment_index))
        selected_links = [links[link_id] for link_id in crossing_ids]
        signal_ids = selected_signal_ids(
            route_coordinates,
            selected_links,
            safety_index["signal"],
            threshold_m=signal_match_threshold_m,
        )
        # CCTV is not a crossing event. Preserve its already-precomputed
        # route-adjacent value rather than doing another full spatial batch.
        cctv_count = properties.get("cctv_location_count")
        if cctv_count is None:
            raise SafetyInputError(
                f"Route feature {feature_index}: cctv_location_count is required from the existing safety batch."
            )
        try:
            cctv_count = int(cctv_count)
        except (TypeError, ValueError) as exc:
            raise SafetyInputError(f"Route feature {feature_index}: cctv_location_count must be an integer.") from exc
        if cctv_count < 0:
            raise SafetyInputError(f"Route feature {feature_index}: cctv_location_count must not be negative.")
        signal_sets = {link_id: [] for link_id in crossing_ids}
        for signal_id in signal_ids:
            # A signal can control more than one nearby crossing.  Assign it
            # to its closest traversed crossing solely for map presentation;
            # the route-level count remains distinct by signal ID.
            signal_point = signal_points_by_id[signal_id]
            closest_link = min(
                selected_links,
                key=lambda link: distance_to_link_meters(signal_point[0], signal_point[1], link),
            )
            signal_sets[closest_link.link_id].append({
                "id": signal_id,
                "longitude": round(signal_point[0], COORDINATE_DECIMALS),
                "latitude": round(signal_point[1], COORDINATE_DECIMALS),
            })
        events = [
            {
                "crosswalk_link_id": link.link_id,
                "longitude": round(link.midpoint[0], COORDINATE_DECIMALS),
                "latitude": round(link.midpoint[1], COORDINATE_DECIMALS),
                "pedestrian_signals": signal_sets[link.link_id],
            }
            for link in selected_links
        ]
        properties.update({
            "safety_match_threshold_m": None,
            "crosswalk_count": len(crossing_ids),
            "pedestrian_signal_count": len(signal_ids),
            "cctv_location_count": cctv_count,
            "route_crossing_events": events,
            "safety_calculation_version": CALCULATION_VERSION,
            "safety_calculated_at": calculated_at,
        })
        totals["crosswalk"] += len(crossing_ids)
        totals["signal"] += len(signal_ids)
        totals["cctv"] += cctv_count
    return totals


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pre-compute actual crossing and crossing-signal events for stored walking routes.")
    parser.add_argument("--input", type=Path, action="append", required=True, help="Route GeoJSON; repeat for each input export.")
    parser.add_argument("--walking-links", type=Path, required=True, help="OA-21208 walking-links GeoJSON containing the crosswalk flag.")
    parser.add_argument("--safety-points", type=Path, required=True, help="Local JSON containing crosswalk, signal, and CCTV point coordinates.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--signal-match-threshold-m", type=int, default=DEFAULT_SIGNAL_MATCH_THRESHOLD_M)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.signal_match_threshold_m <= 0:
        raise SafetyInputError("signal-match-threshold-m must be positive.")
    safety_points = load_safety_points(args.safety_points)
    links, segment_index = load_crosswalk_link_index(args.walking_links)
    calculated_at = datetime.now(ZoneInfo("Asia/Seoul")).isoformat()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for input_path in args.input:
        collection = load_feature_collection(input_path)
        totals = attach_crossing_events(
            collection,
            links=links,
            crosswalk_segment_index=segment_index,
            safety_points=safety_points,
            signal_match_threshold_m=args.signal_match_threshold_m,
            calculated_at=calculated_at,
        )
        output_path = args.output_dir / input_path.name
        output_path.write_text(json.dumps(collection, ensure_ascii=False), encoding="utf-8")
        source_metadata = input_path.with_name(input_path.stem + "_metadata.json")
        output_metadata = output_path.with_name(output_path.stem + "_metadata.json")
        if source_metadata.is_file():
            metadata = json.loads(source_metadata.read_text(encoding="utf-8"))
            metadata["route_crossing_events"] = {
                "crosswalk_source": "oa21208_walking_link_crosswalk_flag",
                "signal_match_threshold_m": args.signal_match_threshold_m,
                "calculation_version": CALCULATION_VERSION,
                "calculated_at": calculated_at,
                "counts": totals,
            }
            output_metadata.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
        outputs.append({"input": str(input_path), "output": str(output_path), "routeCount": len(collection["features"]), "counts": totals})
    print(json.dumps({"calculatedAt": calculated_at, "outputs": outputs}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
