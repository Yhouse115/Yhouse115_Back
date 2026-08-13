from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "load_environment_data.py"
SPEC = importlib.util.spec_from_file_location("load_environment_data", SCRIPT_PATH)
assert SPEC and SPEC.loader
loader = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = loader
SPEC.loader.exec_module(loader)


def test_transport_loader_uses_boundary_bus_when_profile_stop_is_outside_yangcheon() -> None:
    datasets: dict[str, dict[str, object]] = {}
    access, summaries = loader.build_transport_rows(
        [
            {
                "complex_id": "CX-001",
                "main_origin_id": "CX-001-E01",
                "origin_method": "complex_center",
                "access_reference_date": "2026-08-11",
                "nearest_subway_exit": "101",
                "nearest_subway_station": "오목교",
                "nearest_subway_line": "5호선",
                "subway_straight_distance_m": "200.0",
                "subway_walk_distance_m": "300.0",
                "subway_walk_time_min": "4.2",
                "nearest_bus_stop_id": "OUTSIDE-1",
                "nearest_bus_stop_name": "경계정류장",
                "bus_stop_walk_distance_m": "120.0",
                "bus_stop_walk_time_min": "1.7",
                "bus_stop_count_500m": "7",
                "route_method": "walking_network",
                "failure_reason": "",
                "qa_flags": "",
            }
        ],
        {"transit_subway_exit:101", "transit_bus_stop:OUTSIDE-1"},
        datasets,
    )

    assert {row["feature_id"] for row in access} == {"transit_subway_exit:101", "transit_bus_stop:OUTSIDE-1"}
    bus_summary = next(row for row in summaries if row["access_group"] == "bus_stop")
    assert loader.parse_json_object(bus_summary["metrics"], "metrics")["busStopCountWithin500WalkMeters"] == 7


def test_emit_psql_import_uses_composite_conflict_key_and_postgres_arrays() -> None:
    stream = io.StringIO()
    loader.emit_psql_import(
        {
            "source_dataset": [
                {
                    "source_dataset_id": "source-a",
                    "source_name": "Source A",
                    "source_file": None,
                    "source_sha256": None,
                    "reference_date": None,
                    "license_name": None,
                    "metadata": "{}",
                }
            ],
            "apartment_complex": [
                {
                    "complex_id": "CX-001",
                    "name": "테스트단지",
                    "admin_dong_code": None,
                    "admin_dong_name": None,
                    "legal_dong_code": None,
                    "road_address": None,
                    "parcel_address": None,
                    "household_count": None,
                    "building_count": None,
                    "approval_date": None,
                    "longitude": 126.8,
                    "latitude": 37.5,
                    "coordinate_method": "test",
                    "coordinate_confidence": None,
                    "complex_status": "active",
                    "master_reference_date": None,
                    "qa_flags": ["qa_flag"],
                }
            ],
            "environment_feature": [
                {
                    "feature_id": "feature-1",
                    "source_dataset_id": "source-a",
                    "source_record_id": "1",
                    "layer_category": "healthcare",
                    "feature_type": "pediatrics",
                    "service_types": ["pediatrics"],
                    "name": "테스트의원",
                    "address": None,
                    "longitude": 126.8,
                    "latitude": 37.5,
                    "coordinate_status": "verified_wgs84",
                    "coordinate_method": "test",
                    "record_status": "active",
                    "reference_date": None,
                    "attributes": "{}",
                    "qa_flags": [],
                }
            ],
            "complex_feature_access": [
                {
                    "complex_id": "CX-001",
                    "feature_id": "feature-1",
                    "access_group": "pediatrics",
                    "main_origin_id": "CX-001-E01",
                    "origin_method": "complex_center",
                    "calculation_version": "v1",
                    "policy_version": "policy-v1",
                    "reference_date": None,
                    "straight_distance_m": None,
                    "walk_distance_m": 420.0,
                    "walk_time_min": 6.0,
                    "distance_method": "walking_network",
                    "access_status": "available",
                    "category_distance_limit_m": 1000.0,
                    "is_nearest": True,
                    "selection_reason": "nearest",
                    "failure_reason": None,
                    "qa_flags": [],
                }
            ],
            "complex_environment_summary": [
                {
                    "complex_id": "CX-001",
                    "access_group": "pediatrics",
                    "main_origin_id": "CX-001-E01",
                    "origin_method": "complex_center",
                    "calculation_version": "v1",
                    "policy_version": "policy-v1",
                    "reference_date": None,
                    "category_distance_limit_m": 1000.0,
                    "nearest_feature_id": "feature-1",
                    "nearest_walk_distance_m": 420.0,
                    "nearest_walk_time_min": 6.0,
                    "count_within_5min": 0,
                    "count_within_10min": 1,
                    "count_within_15min": 1,
                    "selected_feature_count": 1,
                    "metrics": "{}",
                    "summary_status": "available",
                    "failure_reason": None,
                    "qa_flags": [],
                }
            ],
        },
        stream,
    )

    output = stream.getvalue()
    assert "COPY \"_environment_import_1\"" in output
    assert 'ON CONFLICT ("complex_id", "feature_id", "access_group", "main_origin_id", "calculation_version") DO UPDATE' in output
    assert '"qa_flag"' in output
