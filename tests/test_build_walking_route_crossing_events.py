from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from build_walking_route_crossing_events import attach_crossing_events, crosswalk_node_index
from build_walking_route_safety_counts import indexed_points


def test_actual_crossing_requires_an_exact_crosswalk_node_and_clusters_duplicate_nodes() -> None:
    collection = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {"cctv_location_count": 1},
            "geometry": {"type": "LineString", "coordinates": [[126.8599, 37.5200], [126.8600, 37.5200], [126.8601, 37.5200], [126.8620, 37.5200]]},
        }],
    }
    safety_points = {
        "crosswalk": [
            ("crossing-a", 126.8600, 37.5200),
            ("crossing-b", 126.8601, 37.5200),
            ("near-but-not-on-route", 126.8610, 37.52005),
        ],
        "signal": [("on-crossing", 126.86005, 37.52005), ("on-footpath", 126.8618, 37.5200)],
        "cctv": [],
    }
    totals = attach_crossing_events(
        collection,
        crosswalk_nodes=crosswalk_node_index(safety_points["crosswalk"]),
        signal_index=indexed_points({"signal": safety_points["signal"]}, 0.002)["signal"],
        signal_match_threshold_m=20,
        event_cluster_distance_m=20,
        calculated_at="2026-08-14T00:00:00+09:00",
    )

    properties = collection["features"][0]["properties"]
    assert totals == {"crosswalk": 1, "signal": 1, "cctv": 1}
    assert properties["crosswalk_count"] == 1
    assert properties["pedestrian_signal_count"] == 1
    assert properties["route_crossing_events"] == [{
        "crosswalk_event_id": "node:crossing-a+crossing-b",
        "longitude": 126.86005,
        "latitude": 37.52,
        "pedestrian_signals": [{"id": "on-crossing", "longitude": 126.86005, "latitude": 37.52005}],
    }]
