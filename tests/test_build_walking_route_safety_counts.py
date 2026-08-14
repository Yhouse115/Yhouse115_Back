from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from build_walking_route_safety_counts import attach_counts, indexed_points


def test_safety_counts_use_distance_to_route_line_not_only_vertices() -> None:
    collection = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {},
            "geometry": {"type": "LineString", "coordinates": [[126.8600, 37.5200], [126.8620, 37.5200]]},
        }],
    }
    points = {
        "crosswalk": [("crossing-on-line", 126.8610, 37.52010), ("crossing-outside", 126.8610, 37.52030)],
        "signal": [("signal-on-line", 126.8615, 37.51995)],
        "cctv": [("camera-on-line", 126.8605, 37.52005)],
    }

    totals = attach_counts(
        collection,
        indexed_points(points, 0.002),
        threshold_m=20,
        calculated_at="2026-08-14T01:00:00+09:00",
    )

    assert totals == {"crosswalk": 1, "signal": 1, "cctv": 1}
    assert collection["features"][0]["properties"]["crosswalk_count"] == 1
    assert collection["features"][0]["properties"]["safety_match_threshold_m"] == 20
