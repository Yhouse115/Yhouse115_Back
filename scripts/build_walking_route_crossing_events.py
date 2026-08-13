"""Pre-compute actual crossing events from walking-route graph nodes.

The public OA-21208 ``crosswalk`` link flag is incomplete for the local
network.  Crosswalk source nodes, however, are part of the same graph.  A
crossing event is therefore recorded only when a crosswalk node is an exact
vertex of the reconstructed walking route.  Nodes within 20 m form one visual
crossing event, and pedestrian signals are included only when attached to one
of those selected nodes within 20 m.

This is a local batch tool; it never writes Supabase.
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

from build_walking_route_safety_counts import (
    DEFAULT_GRID_DEGREES,
    SafetyInputError,
    candidate_cells,
    indexed_points,
    load_feature_collection,
    load_safety_points,
)


CALCULATION_VERSION = "route_exact_crosswalk_node_and_signal_20m_v2"
DEFAULT_SIGNAL_MATCH_THRESHOLD_M = 20
DEFAULT_EVENT_CLUSTER_DISTANCE_M = 20
COORDINATE_DECIMALS = 7
EARTH_RADIUS_M = 6_371_000.0


def coordinate_key(longitude: float, latitude: float) -> tuple[float, float]:
    return round(longitude, COORDINATE_DECIMALS), round(latitude, COORDINATE_DECIMALS)


def haversine_meters(first: tuple[float, float], second: tuple[float, float]) -> float:
    longitude_1, latitude_1 = first
    longitude_2, latitude_2 = second
    latitude_delta = math.radians(latitude_2 - latitude_1)
    longitude_delta = math.radians(longitude_2 - longitude_1)
    value = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(math.radians(latitude_1))
        * math.cos(math.radians(latitude_2))
        * math.sin(longitude_delta / 2) ** 2
    )
    return EARTH_RADIUS_M * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def crosswalk_node_index(points: Iterable[tuple[str, float, float]]) -> dict[tuple[float, float], tuple[str, float, float]]:
    result: dict[tuple[float, float], tuple[str, float, float]] = {}
    for identifier, longitude, latitude in points:
        key = coordinate_key(longitude, latitude)
        existing = result.get(key)
        if existing and existing[0] != identifier:
            raise SafetyInputError(f"Crosswalk nodes share a coordinate with different IDs: {existing[0]}/{identifier}")
        result[key] = (identifier, longitude, latitude)
    return result


def selected_crosswalk_nodes(
    route_coordinates: list[list[float]],
    node_index: dict[tuple[float, float], tuple[str, float, float]],
) -> list[tuple[str, float, float]]:
    selected: dict[str, tuple[str, float, float]] = {}
    for coordinate in route_coordinates:
        try:
            longitude, latitude = float(coordinate[0]), float(coordinate[1])
        except (IndexError, TypeError, ValueError) as exc:
            raise SafetyInputError("Route contains an invalid coordinate.") from exc
        node = node_index.get(coordinate_key(longitude, latitude))
        if node:
            selected[node[0]] = node
    return [selected[identifier] for identifier in sorted(selected)]


def clustered_crosswalk_nodes(
    nodes: list[tuple[str, float, float]],
    *,
    cluster_distance_m: float,
) -> list[list[tuple[str, float, float]]]:
    """Group duplicate source nodes belonging to one visual crossing event."""
    parents = list(range(len(nodes)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(first: int, second: int) -> None:
        root_first, root_second = find(first), find(second)
        if root_first != root_second:
            parents[root_second] = root_first

    for index, node in enumerate(nodes):
        for previous_index, previous in enumerate(nodes[:index]):
            if haversine_meters((node[1], node[2]), (previous[1], previous[2])) <= cluster_distance_m:
                union(index, previous_index)

    grouped: dict[int, list[tuple[str, float, float]]] = defaultdict(list)
    for index, node in enumerate(nodes):
        grouped[find(index)].append(node)
    return [grouped[key] for key in sorted(grouped)]


def candidate_signals(
    route_coordinates: list[list[float]],
    signal_index: dict[tuple[int, int], list[tuple[str, float, float]]],
    *,
    threshold_m: float,
) -> list[tuple[str, float, float]]:
    candidates: dict[str, tuple[str, float, float]] = {}
    for cell in candidate_cells(route_coordinates, threshold_m=threshold_m, grid_degrees=DEFAULT_GRID_DEGREES):
        for signal in signal_index.get(cell, []):
            candidates[signal[0]] = signal
    return [candidates[identifier] for identifier in sorted(candidates)]


def crossing_events(
    groups: list[list[tuple[str, float, float]]],
    signals: list[tuple[str, float, float]],
    *,
    signal_match_threshold_m: float,
) -> list[dict[str, Any]]:
    events = []
    assigned_signal_ids: set[str] = set()
    for group in groups:
        event_signals = []
        for signal_id, signal_longitude, signal_latitude in signals:
            if signal_id in assigned_signal_ids:
                continue
            if any(
                haversine_meters((signal_longitude, signal_latitude), (longitude, latitude)) <= signal_match_threshold_m
                for _, longitude, latitude in group
            ):
                event_signals.append({
                    "id": signal_id,
                    "longitude": round(signal_longitude, COORDINATE_DECIMALS),
                    "latitude": round(signal_latitude, COORDINATE_DECIMALS),
                })
                assigned_signal_ids.add(signal_id)
        # Keep a stable route-event key while retaining every raw source node
        # as diagnostics. The midpoint is for one uncluttered map marker.
        link_id = "node:" + "+".join(node[0] for node in group)
        events.append({
            "crosswalk_event_id": link_id,
            "longitude": round(sum(node[1] for node in group) / len(group), COORDINATE_DECIMALS),
            "latitude": round(sum(node[2] for node in group) / len(group), COORDINATE_DECIMALS),
            "pedestrian_signals": event_signals,
        })
    return events


def attach_crossing_events(
    collection: dict[str, Any],
    *,
    crosswalk_nodes: dict[tuple[float, float], tuple[str, float, float]],
    signal_index: dict[tuple[int, int], list[tuple[str, float, float]]],
    signal_match_threshold_m: int,
    event_cluster_distance_m: int,
    calculated_at: str,
) -> dict[str, int]:
    totals = {"crosswalk": 0, "signal": 0, "cctv": 0}
    for feature_index, feature in enumerate(collection["features"]):
        geometry = feature.get("geometry")
        properties = feature.get("properties")
        coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
        if not isinstance(properties, dict) or not isinstance(geometry, dict) or geometry.get("type") != "LineString" or not isinstance(coordinates, list) or len(coordinates) < 2:
            raise SafetyInputError(f"Route feature {feature_index}: valid LineString and properties are required.")
        route_coordinates = [[float(coordinate[0]), float(coordinate[1])] for coordinate in coordinates]
        groups = clustered_crosswalk_nodes(
            selected_crosswalk_nodes(route_coordinates, crosswalk_nodes),
            cluster_distance_m=event_cluster_distance_m,
        )
        events = crossing_events(
            groups,
            candidate_signals(route_coordinates, signal_index, threshold_m=signal_match_threshold_m),
            signal_match_threshold_m=signal_match_threshold_m,
        )
        cctv_count = properties.get("cctv_location_count")
        try:
            cctv_count = int(cctv_count)
        except (TypeError, ValueError) as exc:
            raise SafetyInputError(f"Route feature {feature_index}: cctv_location_count from the existing batch is required.") from exc
        if cctv_count < 0:
            raise SafetyInputError(f"Route feature {feature_index}: cctv_location_count must not be negative.")
        signal_count = sum(len(event["pedestrian_signals"]) for event in events)
        properties.update({
            "safety_match_threshold_m": None,
            "crosswalk_count": len(events),
            "pedestrian_signal_count": signal_count,
            "cctv_location_count": cctv_count,
            "route_crossing_events": events,
            "safety_calculation_version": CALCULATION_VERSION,
            "safety_calculated_at": calculated_at,
        })
        totals["crosswalk"] += len(events)
        totals["signal"] += signal_count
        totals["cctv"] += cctv_count
    return totals


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pre-compute actual crosswalk-node events for stored walking routes.")
    parser.add_argument("--input", type=Path, action="append", required=True, help="Route GeoJSON; repeat for each input export.")
    parser.add_argument("--safety-points", type=Path, required=True, help="Local JSON containing crosswalk, signal, and CCTV point coordinates.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--signal-match-threshold-m", type=int, default=DEFAULT_SIGNAL_MATCH_THRESHOLD_M)
    parser.add_argument("--event-cluster-distance-m", type=int, default=DEFAULT_EVENT_CLUSTER_DISTANCE_M)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.signal_match_threshold_m <= 0 or args.event_cluster_distance_m <= 0:
        raise SafetyInputError("safety thresholds must be positive.")
    safety_points = load_safety_points(args.safety_points)
    crosswalk_nodes = crosswalk_node_index(safety_points["crosswalk"])
    signal_index = indexed_points({"signal": safety_points["signal"]}, DEFAULT_GRID_DEGREES)["signal"]
    calculated_at = datetime.now(ZoneInfo("Asia/Seoul")).isoformat()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for input_path in args.input:
        collection = load_feature_collection(input_path)
        totals = attach_crossing_events(
            collection,
            crosswalk_nodes=crosswalk_nodes,
            signal_index=signal_index,
            signal_match_threshold_m=args.signal_match_threshold_m,
            event_cluster_distance_m=args.event_cluster_distance_m,
            calculated_at=calculated_at,
        )
        output_path = args.output_dir / input_path.name
        output_path.write_text(json.dumps(collection, ensure_ascii=False), encoding="utf-8")
        source_metadata = input_path.with_name(input_path.stem + "_metadata.json")
        output_metadata = output_path.with_name(output_path.stem + "_metadata.json")
        if source_metadata.is_file():
            metadata = json.loads(source_metadata.read_text(encoding="utf-8"))
            metadata["route_crossing_events"] = {
                "crosswalk_source": "exact_crosswalk_node_on_oa21208_route",
                "signal_match_threshold_m": args.signal_match_threshold_m,
                "event_cluster_distance_m": args.event_cluster_distance_m,
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
