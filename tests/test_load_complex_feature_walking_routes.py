from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from load_complex_feature_walking_routes import RouteInputError, route_rows_from_geojson


def write_geojson(path: Path, *, distance: float = 532.4) -> None:
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {
                            "complex_id": "CX-001",
                            "school_feature_id": "education_elementary_yangcheon:7081453",
                            "feature_type": "elementary_school",
                            "origin_method": "complex_center",
                            "route_method": "local_dijkstra",
                            "walk_distance_m": distance,
                            "walk_time_min": 7.61,
                            "graph_distance_m": 436.6,
                            "origin_snap_distance_m": 41.2,
                            "destination_snap_distance_m": 54.7,
                            "qa_flags": "boundary_snap",
                        },
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [[126.8747857, 37.5198083], [126.8744162, 37.5195816]],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_loader_builds_upsert_rows_from_local_geojson(tmp_path: Path) -> None:
    geojson_path = tmp_path / "routes.geojson"
    write_geojson(geojson_path)

    rows = route_rows_from_geojson(
        geojson_path,
        calculation_version="test-v1",
        calculated_at="2026-08-13T16:35:43+09:00",
    )

    assert rows == [
        {
            "complex_id": "CX-001",
            "feature_id": "education_elementary_yangcheon:7081453",
            "access_group": "elementary_school",
            "main_origin_id": "complex_center",
            "calculation_version": "test-v1",
            "route_coordinates": [[126.8747857, 37.5198083], [126.8744162, 37.5195816]],
            "walk_distance_m": 532.4,
            "walk_time_min": 7.61,
            "route_method": "local_dijkstra",
            "calculated_at": "2026-08-13T16:35:43+09:00",
            "route_metadata": {
                "originMethod": "complex_center",
                "graphDistanceMeters": 436.6,
                "originSnapDistanceMeters": 41.2,
                "destinationSnapDistanceMeters": 54.7,
                "accessDistanceDeltaMeters": None,
            },
            "qa_flags": ["boundary_snap"],
            "safety_match_threshold_m": None,
            "crosswalk_count": None,
            "pedestrian_signal_count": None,
            "cctv_location_count": None,
            "route_crossing_events": None,
            "safety_calculation_version": None,
            "safety_calculated_at": None,
        }
    ]


def test_loader_rejects_routes_at_or_above_one_point_five_kilometers(tmp_path: Path) -> None:
    geojson_path = tmp_path / "routes.geojson"
    write_geojson(geojson_path, distance=1500.0)

    with pytest.raises(RouteInputError, match="below 1500 m"):
        route_rows_from_geojson(
            geojson_path,
            calculation_version="test-v1",
            calculated_at="2026-08-13T16:35:43+09:00",
        )


def test_loader_accepts_a_three_kilometer_park_route_when_explicitly_allowed(tmp_path: Path) -> None:
    geojson_path = tmp_path / "park-routes.geojson"
    write_geojson(geojson_path, distance=2999.9)

    rows = route_rows_from_geojson(
        geojson_path,
        calculation_version="test-v1",
        calculated_at="2026-08-13T16:35:43+09:00",
        max_stored_walk_distance_m=3000,
    )

    assert rows[0]["walk_distance_m"] == 2999.9


def test_loader_keeps_precomputed_twenty_meter_safety_counts(tmp_path: Path) -> None:
    geojson_path = tmp_path / "routes.geojson"
    write_geojson(geojson_path)
    collection = json.loads(geojson_path.read_text(encoding="utf-8"))
    collection["features"][0]["properties"].update({
        "safety_match_threshold_m": 20,
        "crosswalk_count": 8,
        "pedestrian_signal_count": 2,
        "cctv_location_count": 11,
        "safety_calculation_version": "route_safety_20m_v1",
        "safety_calculated_at": "2026-08-14T01:00:00+09:00",
    })
    geojson_path.write_text(json.dumps(collection), encoding="utf-8")

    row = route_rows_from_geojson(
        geojson_path,
        calculation_version="test-v1",
        calculated_at="2026-08-13T16:35:43+09:00",
    )[0]

    assert row["safety_match_threshold_m"] == 20
    assert row["crosswalk_count"] == 8
    assert row["pedestrian_signal_count"] == 2
    assert row["cctv_location_count"] == 11


def test_loader_accepts_actual_crossing_events_and_requires_matching_counts(tmp_path: Path) -> None:
    geojson_path = tmp_path / "routes.geojson"
    write_geojson(geojson_path)
    collection = json.loads(geojson_path.read_text(encoding="utf-8"))
    collection["features"][0]["properties"].update({
        "crosswalk_count": 1,
        "pedestrian_signal_count": 1,
        "route_crossing_events": [{
            "crosswalk_event_id": "node:229944",
            "longitude": 126.8745,
            "latitude": 37.5196,
            "pedestrian_signals": [{"id": "25-0000004005", "longitude": 126.8745, "latitude": 37.5196}],
        }],
    })
    geojson_path.write_text(json.dumps(collection), encoding="utf-8")

    row = route_rows_from_geojson(
        geojson_path,
        calculation_version="test-v1",
        calculated_at="2026-08-13T16:35:43+09:00",
    )[0]

    assert row["route_crossing_events"] == [{
        "crosswalk_event_id": "node:229944",
        "longitude": 126.8745,
        "latitude": 37.5196,
        "pedestrian_signals": [{"id": "25-0000004005", "longitude": 126.8745, "latitude": 37.5196}],
    }]
