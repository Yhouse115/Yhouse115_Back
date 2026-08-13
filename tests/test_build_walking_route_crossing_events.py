from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from build_walking_route_crossing_events import attach_crossing_events, load_crosswalk_link_index


def test_actual_crossing_requires_a_flagged_walking_link(tmp_path) -> None:
    walking_links = tmp_path / "walking_links.geojson"
    walking_links.write_text(
        """{"type":"FeatureCollection","features":[
        {"type":"Feature","properties":{"link_id":"crossing-link","crosswalk":"1"},"geometry":{"type":"LineString","coordinates":[[126.8600,37.5200],[126.8610,37.5200]]}},
        {"type":"Feature","properties":{"link_id":"footpath-link","crosswalk":"0"},"geometry":{"type":"LineString","coordinates":[[126.8610,37.5200],[126.8620,37.5200]]}}
        ]}""",
        encoding="utf-8",
    )
    links, segment_index = load_crosswalk_link_index(walking_links)
    collection = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {"cctv_location_count": 1},
            "geometry": {"type": "LineString", "coordinates": [[126.8599, 37.5200], [126.8600, 37.5200], [126.8610, 37.5200], [126.8620, 37.5200]]},
        }],
    }
    safety_points = {
        "crosswalk": [],
        "signal": [("on-crossing", 126.8605, 37.52005), ("on-footpath", 126.8618, 37.5200)],
        "cctv": [("near-route", 126.8615, 37.5201)],
    }

    totals = attach_crossing_events(
        collection,
        links=links,
        crosswalk_segment_index=segment_index,
        safety_points=safety_points,
        signal_match_threshold_m=20,
        calculated_at="2026-08-14T00:00:00+09:00",
    )

    properties = collection["features"][0]["properties"]
    assert totals == {"crosswalk": 1, "signal": 1, "cctv": 1}
    assert properties["crosswalk_count"] == 1
    assert properties["pedestrian_signal_count"] == 1
    assert properties["route_crossing_events"] == [{
        "crosswalk_link_id": "crossing-link",
        "longitude": 126.8605,
        "latitude": 37.52,
        "pedestrian_signals": [{"id": "on-crossing", "longitude": 126.8605, "latitude": 37.52005}],
    }]
