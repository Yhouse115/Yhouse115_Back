from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from load_complex_feature_access import read_rows


def test_compact_access_loader_keeps_distance_time_without_route_geometry(tmp_path: Path) -> None:
    source = tmp_path / "access.csv"
    source.write_text(
        "complex_id,feature_id,access_group,main_origin_id,origin_method,calculation_version,policy_version,reference_date,straight_distance_m,walk_distance_m,walk_time_min,distance_method,access_status,category_distance_limit_m,is_nearest,selection_reason,qa_flags\n"
        "CX-001,healthcare_hospitals_seoul:A1,medical_clinic,complex_center,complex_center,v1,p1,2026-08-14,100.5,270.8,3.87,walking_network,available,2000,true,within_category_limit,boundary_snap\n",
        encoding="utf-8-sig",
    )

    rows = read_rows(source, access_group="medical_clinic")

    assert rows == [{
        "complex_id": "CX-001", "feature_id": "healthcare_hospitals_seoul:A1", "access_group": "medical_clinic",
        "main_origin_id": "complex_center", "origin_method": "complex_center", "calculation_version": "v1",
        "policy_version": "p1", "reference_date": "2026-08-14", "straight_distance_m": 100.5,
        "walk_distance_m": 270.8, "walk_time_min": 3.87, "distance_method": "walking_network",
        "access_status": "available", "category_distance_limit_m": 2000.0, "is_nearest": True,
        "selection_reason": "within_category_limit", "failure_reason": None, "qa_flags": ["boundary_snap"],
    }]
