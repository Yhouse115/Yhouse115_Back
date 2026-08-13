"""Pre-compute Yangcheon daily-convenience walking access and load Supabase.

This fills the existing `complex_feature_access` and
`complex_environment_summary` serving tables. It uses the local OA-21208
walking graph; no distance or count is calculated while serving an API request.
"""

from __future__ import annotations

import argparse
import csv
import heapq
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from scripts.load_environment_serving_to_supabase import SupabaseRest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = BACKEND_ROOT.parents[2]
ACCESSIBILITY_SCRIPTS = WORKSPACE_ROOT / "work" / "02_accessibility" / "scripts"
sys.path.insert(0, str(ACCESSIBILITY_SCRIPTS))
import accessibility_pipeline as walking  # noqa: E402


PROFILE_PATH = WORKSPACE_ROOT / "work" / "07_yangcheon_gu" / "05_integration" / "complex_transport_profile.csv"
NETWORK_ROOT = WORKSPACE_ROOT / "work" / "09_environment" / "intermediate" / "oa21208_yangcheon_guro_extended_20260812"
NODES_PATH = NETWORK_ROOT / "walking_nodes.geojson"
LINKS_PATH = NETWORK_ROOT / "walking_links.geojson"

ACCESS_GROUP = "daily_convenience"
CALCULATION_VERSION = "oa21208_yangcheon_guro_extended_20260812_daily_convenience_v1"
POLICY_VERSION = "daily_convenience_access_policy_20260813_v1"
REFERENCE_DATE = "2026-08-13"
WALKING_SPEED_M_PER_MIN = 70.0
MAX_SNAP_DISTANCE_M = 250.0
SEARCH_DISTANCE_M = 3_500.0
WITHIN_COUNT_DISTANCE_M = 500.0
DETAIL_DISTANCE_LIMIT_M = 500.0


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def dijkstra_distances(graph: walking.Graph, source: str, max_distance_m: float) -> dict[str, float]:
    distances = {source: 0.0}
    queue: list[tuple[float, str]] = [(0.0, source)]
    while queue:
        distance, node = heapq.heappop(queue)
        if distance != distances.get(node):
            continue
        if distance > max_distance_m:
            break
        for edge in graph.adjacency.get(node, []):
            candidate = distance + edge.weight
            if candidate <= max_distance_m and candidate < distances.get(edge.target, math.inf):
                distances[edge.target] = candidate
                heapq.heappush(queue, (candidate, edge.target))
    return distances


def largest_component_nodes(graph: walking.Graph) -> set[str]:
    undirected: dict[str, set[str]] = defaultdict(set)
    for source, edges in graph.adjacency.items():
        for edge in edges:
            undirected[source].add(edge.target)
            undirected[edge.target].add(source)
    unseen = set(graph.nodes)
    largest: set[str] = set()
    while unseen:
        start = unseen.pop()
        component = {start}
        stack = [start]
        while stack:
            node = stack.pop()
            for neighbor in undirected.get(node, set()):
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    component.add(neighbor)
                    stack.append(neighbor)
        if len(component) > len(largest):
            largest = component
    return largest


def routable_node(
    coordinate: tuple[float, float],
    index: walking.NodeIndex,
    primary_index: walking.NodeIndex,
    primary_nodes: set[str],
) -> tuple[str | None, float]:
    node_id, snap_m = index.nearest(coordinate)
    if node_id in primary_nodes:
        return node_id, snap_m
    primary_id, primary_snap_m = primary_index.nearest(coordinate)
    if primary_id and primary_snap_m <= MAX_SNAP_DISTANCE_M:
        return primary_id, primary_snap_m
    return node_id, snap_m


def _target(
    row: dict[str, Any],
    index: walking.NodeIndex,
    primary_index: walking.NodeIndex,
    primary_nodes: set[str],
) -> dict[str, Any] | None:
    coordinate = (float(row["longitude"]), float(row["latitude"]))
    node_id, snap_m = routable_node(coordinate, index, primary_index, primary_nodes)
    if not node_id or snap_m > MAX_SNAP_DISTANCE_M:
        return None
    return {**row, "coordinate": coordinate, "node_id": node_id, "snap_m": snap_m}


def _distance(origin: dict[str, Any], target: dict[str, Any], distances: dict[str, float]) -> float | None:
    graph_distance = distances.get(target["node_id"])
    if graph_distance is None:
        return None
    return origin["snap_m"] + graph_distance + target["snap_m"]


def build_payloads(rest: SupabaseRest) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    required = (PROFILE_PATH, NODES_PATH, LINKS_PATH)
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Required input is missing: " + ", ".join(missing))
    remote = rest.fetch_all(
        "environment_feature",
        "feature_id,feature_type,name,longitude,latitude,axis,record_status",
    )
    source_features = [
        row
        for row in remote
        if row.get("axis") == "daily_convenience"
        and row.get("feature_type") in {"mart", "convenience_store", "daily_commerce"}
        and row.get("record_status") != "inactive"
    ]
    graph = walking.load_graph(NODES_PATH, LINKS_PATH)
    index = walking.NodeIndex(graph.nodes)
    primary_nodes = largest_component_nodes(graph)
    primary_index = walking.NodeIndex({node_id: graph.nodes[node_id] for node_id in primary_nodes})
    targets = [
        target
        for row in source_features
        if (target := _target(row, index, primary_index, primary_nodes))
    ]
    mart_targets = [target for target in targets if target["feature_type"] == "mart"]
    if not targets:
        raise RuntimeError("No routable daily-convenience features are available")

    access_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for profile in read_csv(PROFILE_PATH):
        complex_id = profile.get("complex_id", "").strip()
        origin_id = profile.get("main_origin_id", "").strip()
        origin_method = profile.get("origin_method", "").strip()
        longitude = float(profile["longitude"])
        latitude = float(profile["latitude"])
        node_id, snap_m = routable_node((longitude, latitude), index, primary_index, primary_nodes)
        if not complex_id or not origin_id or not origin_method or not node_id or snap_m > MAX_SNAP_DISTANCE_M:
            raise RuntimeError(f"Invalid or unroutable apartment origin: {complex_id}")
        origin = {"coordinate": (longitude, latitude), "node_id": node_id, "snap_m": snap_m}
        distances = dijkstra_distances(graph, node_id, SEARCH_DISTANCE_M)
        candidates = [
            (distance, target)
            for target in targets
            if (distance := _distance(origin, target, distances)) is not None
        ]
        candidates.sort(key=lambda item: (item[0], item[1]["feature_id"]))
        if not candidates:
            raise RuntimeError(f"No daily-convenience route within {SEARCH_DISTANCE_M}m: {complex_id}")
        marts = [(distance, target) for distance, target in candidates if target["feature_type"] == "mart"]
        nearest_distance, nearest_target = candidates[0]
        nearest_mart = marts[0] if marts else None
        within_500 = [(distance, target) for distance, target in candidates if distance <= WITHIN_COUNT_DISTANCE_M]
        selected = [(distance, target) for distance, target in candidates if distance <= DETAIL_DISTANCE_LIMIT_M]
        if not selected:
            selected = [(nearest_distance, nearest_target)]
        for distance, target in selected:
            access_rows.append(
                {
                    "complex_id": complex_id,
                    "feature_id": target["feature_id"],
                    "access_group": ACCESS_GROUP,
                    "main_origin_id": origin_id,
                    "origin_method": origin_method,
                    "calculation_version": CALCULATION_VERSION,
                    "policy_version": POLICY_VERSION,
                    "reference_date": REFERENCE_DATE,
                    "straight_distance_m": round(walking.haversine(origin["coordinate"], target["coordinate"]), 1),
                    "walk_distance_m": round(distance, 1),
                    "walk_time_min": round(distance / WALKING_SPEED_M_PER_MIN, 2),
                    "distance_method": "walking_network",
                    "access_status": "available",
                    "category_distance_limit_m": DETAIL_DISTANCE_LIMIT_M,
                    "is_nearest": target["feature_id"] == nearest_target["feature_id"],
                    "selection_reason": "within_500m" if distance <= DETAIL_DISTANCE_LIMIT_M else "nearest_outside_limit",
                    "failure_reason": None,
                    "qa_flags": [],
                }
            )
        metrics: dict[str, Any] = {
            "convenienceCountWithin500WalkMeters": len(within_500),
            "nearestConvenienceName": nearest_target.get("name"),
        }
        if nearest_mart:
            mart_distance, mart_target = nearest_mart
            metrics.update(
                {
                    "nearestMartName": mart_target.get("name"),
                    "nearestMartWalkDistanceMeters": round(mart_distance, 1),
                    "nearestMartWalkTimeMinutes": round(mart_distance / WALKING_SPEED_M_PER_MIN, 2),
                }
            )
        summary_rows.append(
            {
                "complex_id": complex_id,
                "access_group": ACCESS_GROUP,
                "main_origin_id": origin_id,
                "origin_method": origin_method,
                "calculation_version": CALCULATION_VERSION,
                "policy_version": POLICY_VERSION,
                "reference_date": REFERENCE_DATE,
                "category_distance_limit_m": DETAIL_DISTANCE_LIMIT_M,
                "nearest_feature_id": nearest_target["feature_id"],
                "nearest_walk_distance_m": round(nearest_distance, 1),
                "nearest_walk_time_min": round(nearest_distance / WALKING_SPEED_M_PER_MIN, 2),
                "count_within_5min": sum(distance <= 350 for distance, _ in candidates),
                "count_within_10min": sum(distance <= 700 for distance, _ in candidates),
                "count_within_15min": sum(distance <= 1050 for distance, _ in candidates),
                "selected_feature_count": len(selected),
                "metrics": metrics,
                "summary_status": "available",
                "failure_reason": None,
                "qa_flags": [],
            }
        )
    qa = {
        "complex_count": len(summary_rows),
        "remote_feature_count": len(source_features),
        "routable_feature_count": len(targets),
        "access_row_count": len(access_rows),
        "summary_row_count": len(summary_rows),
        "calculation_version": CALCULATION_VERSION,
    }
    return access_rows, summary_rows, qa


def main() -> int:
    parser = argparse.ArgumentParser(description="Calculate daily-convenience walking access and load Supabase")
    parser.add_argument("--apply", action="store_true", help="Upsert calculated serving rows")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 1_000:
        raise ValueError("batch-size must be between 1 and 1000")
    rest = SupabaseRest()
    access_rows, summary_rows, qa = build_payloads(rest)
    if args.apply:
        rest.upsert(
            "complex_feature_access",
            access_rows,
            ("complex_id", "feature_id", "access_group", "main_origin_id", "calculation_version"),
            args.batch_size,
        )
        rest.upsert(
            "complex_environment_summary",
            summary_rows,
            ("complex_id", "access_group", "calculation_version"),
            args.batch_size,
        )
        qa["status"] = "APPLIED"
    else:
        qa["status"] = "READY_TO_APPLY"
    print(json.dumps(qa, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)
