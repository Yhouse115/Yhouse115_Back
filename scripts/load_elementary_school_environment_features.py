"""Load normalized education-care POIs required by stored walking routes.

The route export uses the normalized environment feature IDs from
``environment_features.csv``.  It can publish elementary schools, child-care
centres, and kindergartens (and their source-dataset records) before the route
loader writes rows that reference them.

It is intentionally dry-run by default and uses the service-role REST API
only when ``--apply`` is given.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from load_complex_feature_walking_routes import configured_value


WORKSPACE = Path(__file__).resolve().parents[4]
DEFAULT_INPUT = WORKSPACE / "data" / "processed" / "environment" / "pois" / "environment_features.csv"
SUPPORTED_FEATURE_TYPES = ("elementary_school", "childcare", "kindergarten", "park", "medical_clinic")
FEATURE_TYPE_AXES = {
    "elementary_school": "education_care",
    "childcare": "education_care",
    "kindergarten": "education_care",
    "park": "parks_play",
    "medical_clinic": "medical",
}
SOURCE_DATASET_NAMES = {
    "education_elementary_yangcheon": "Yangcheon elementary schools",
    "education_childcare_yangcheon_20260731": "Yangcheon child-care centres (2026-07-31)",
    "education_kindergarten_yangcheon": "Yangcheon kindergartens",
    "leisure_parks_sinjeong_nearby_2026h1": "Yangcheon and nearby Seoul parks (2026 H1)",
    "healthcare_hospitals_seoul": "Seoul medical facilities",
}
DATASET_UPSERT_COLUMNS = "source_dataset_id"
FEATURE_UPSERT_COLUMNS = "feature_id"


class SchoolInputError(ValueError):
    """Raised when the school POI input cannot be safely published."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def number(value: str | None, field: str, feature_id: str) -> float:
    try:
        result = float(value or "")
    except ValueError as exc:
        raise SchoolInputError(f"{feature_id}: {field} must be numeric") from exc
    if not math.isfinite(result):
        raise SchoolInputError(f"{feature_id}: {field} must be finite")
    return result


def qa_flags(value: str | None) -> list[str]:
    return [flag for flag in (value or "").split("/") if flag]


def parse_attributes(value: str | None, feature_id: str) -> dict[str, Any]:
    try:
        attributes = json.loads(value or "{}")
    except json.JSONDecodeError as exc:
        raise SchoolInputError(f"{feature_id}: attributes_json must be valid JSON") from exc
    if not isinstance(attributes, dict):
        raise SchoolInputError(f"{feature_id}: attributes_json must be an object")
    return attributes


def load_school_rows(
    path: Path,
    feature_types: set[str],
    source_dataset_ids: set[str] | None = None,
    address_contains: str | None = None,
) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"School feature input is missing: {path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))

    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_source_records: set[str] = set()
    for source in source_rows:
        feature_type = source.get("feature_type") or ""
        if feature_type not in feature_types:
            continue
        source_dataset_id = (source.get("source_dataset_id") or "").strip()
        address = source.get("address") or ""
        if source_dataset_ids and source_dataset_id not in source_dataset_ids:
            continue
        if address_contains and address_contains not in address:
            continue
        feature_id = (source.get("feature_id") or "").strip()
        source_record_id = (source.get("source_record_id") or "").strip()
        if not feature_id or not source_record_id:
            raise SchoolInputError("Education-care rows require feature_id and source_record_id")
        if feature_id in seen_ids or source_record_id in seen_source_records:
            raise SchoolInputError(f"Duplicate school feature or source record: {feature_id}")
        seen_ids.add(feature_id)
        seen_source_records.add(source_record_id)
        longitude = number(source.get("longitude"), "longitude", feature_id)
        latitude = number(source.get("latitude"), "latitude", feature_id)
        if not 124 <= longitude <= 132 or not 33 <= latitude <= 39:
            raise SchoolInputError(f"{feature_id}: coordinate is outside the South Korea WGS84 range")
        rows.append(
            {
                "feature_id": feature_id,
                "source_dataset_id": source_dataset_id,
                "source_record_id": source_record_id,
                "layer_category": source.get("layer_category") or "education_childcare",
                "axis": FEATURE_TYPE_AXES[feature_type],
                "feature_type": feature_type,
                "line_names": [],
                "service_types": [],
                "name": source.get("name") or None,
                "address": address or None,
                "scope_role": "yangcheon",
                "longitude": longitude,
                "latitude": latitude,
                "coordinate_status": source.get("coordinate_status") or "unknown",
                "coordinate_method": source.get("coordinate_method") or "unknown",
                "record_status": source.get("record_status") or "unknown",
                "map_visible": True,
                "reference_date": source.get("reference_date") or None,
                "attributes": parse_attributes(source.get("attributes_json"), feature_id),
                "qa_flags": qa_flags(source.get("qa_flags")),
            }
        )
    if not rows:
        raise SchoolInputError("No requested education-care rows were found in the environment feature input")
    return rows


def post_rows(table: str, rows: list[dict[str, Any]], on_conflict: str) -> None:
    supabase_url = configured_value("SUPABASE_URL")
    service_role_key = configured_value("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required with --apply.")
    url = f"{supabase_url.rstrip('/')}/rest/v1/{table}?{urlencode({'on_conflict': on_conflict})}"
    request = Request(
        url,
        data=json.dumps(rows, ensure_ascii=False).encode("utf-8"),
        headers={
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(f"Supabase {table} upsert failed with HTTP {response.status}.")
    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Supabase {table} upsert failed with HTTP {exc.code}: {details}") from exc
    except URLError as exc:
        raise RuntimeError(f"Supabase {table} upsert could not reach the configured project.") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load normalized education-care environment features")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument(
        "--feature-type",
        action="append",
        choices=SUPPORTED_FEATURE_TYPES,
        help="Feature type to publish; may be repeated (defaults to elementary_school for compatibility).",
    )
    parser.add_argument(
        "--source-dataset",
        action="append",
        help="Publish only this normalized source dataset; may be repeated.",
    )
    parser.add_argument(
        "--address-contains",
        help="Publish only facilities whose normalized address contains this text.",
    )
    parser.add_argument("--apply", action="store_true", help="Write rows to Supabase. Omit for validation-only dry run.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    feature_types = set(args.feature_type or ["elementary_school"])
    rows = load_school_rows(
        args.input,
        feature_types,
        set(args.source_dataset) if args.source_dataset else None,
        args.address_contains,
    )
    source_dataset_ids = sorted({str(row["source_dataset_id"]) for row in rows})
    datasets = [
        {
            "source_dataset_id": source_dataset_id,
            "source_name": SOURCE_DATASET_NAMES.get(source_dataset_id, source_dataset_id),
            "source_file": str(args.input),
            "source_sha256": sha256(args.input),
            "reference_date": None,
            "license_name": None,
            "metadata": {"featureTypes": sorted(feature_types), "loader": Path(__file__).name},
        }
        for source_dataset_id in source_dataset_ids
    ]
    if args.apply:
        post_rows("source_dataset", datasets, DATASET_UPSERT_COLUMNS)
        post_rows("environment_feature", rows, FEATURE_UPSERT_COLUMNS)
    print(json.dumps({"status": "APPLIED" if args.apply else "DRY_RUN", "sourceDatasetIds": source_dataset_ids, "featureTypes": sorted(feature_types), "rowCount": len(rows)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
