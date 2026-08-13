"""Validate and optionally load compact walking-access facts into Supabase.

Unlike ``complex_feature_walking_route``, this loader never stores route
coordinates.  It is suitable for categories such as hospitals that should
keep their calculated distance and time without retaining a renderable path.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from load_complex_feature_walking_routes import configured_value

UPSERT_COLUMNS = "complex_id,feature_id,access_group,main_origin_id,calculation_version"


class AccessInputError(ValueError):
    """Raised when an access CSV cannot safely be loaded."""


def optional_number(value: str | None, *, field: str, row_number: int) -> float | None:
    if value is None or not value.strip():
        return None
    try:
        parsed = float(value)
    except ValueError as exc:
        raise AccessInputError(f"Row {row_number}: {field} must be numeric.") from exc
    if parsed < 0:
        raise AccessInputError(f"Row {row_number}: {field} must not be negative.")
    return parsed


def parse_bool(value: str | None, *, field: str, row_number: int) -> bool:
    normalized = (value or "").strip().lower()
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False
    raise AccessInputError(f"Row {row_number}: {field} must be true or false.")


def parse_flags(value: str | None) -> list[str]:
    return [flag for flag in (value or "").split("/") if flag]


def allowed_pairs_from_route_backup(path: Path) -> set[tuple[str, str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AccessInputError(f"Cannot read route backup: {path}") from exc
    if not isinstance(payload, list):
        raise AccessInputError("Route backup must be a JSON array of route rows.")
    pairs = {
        (str(row.get("complex_id") or "").strip(), str(row.get("feature_id") or "").strip())
        for row in payload
        if isinstance(row, dict) and row.get("access_group") == "medical_clinic"
    }
    pairs.discard(("", ""))
    if not pairs:
        raise AccessInputError("Route backup contains no medical_clinic route keys.")
    return pairs


def read_rows(
    path: Path,
    *,
    access_group: str,
    max_walk_distance_m: float | None = None,
    allowed_pairs: set[tuple[str, str]] | None = None,
) -> list[dict[str, Any]]:
    try:
        handle = path.open(encoding="utf-8-sig", newline="")
    except OSError as exc:
        raise AccessInputError(f"Cannot read access CSV: {path}") from exc
    with handle:
        reader = csv.DictReader(handle)
        required = {
            "complex_id", "feature_id", "access_group", "main_origin_id", "origin_method",
            "calculation_version", "reference_date", "walk_distance_m", "walk_time_min",
            "distance_method", "access_status", "category_distance_limit_m", "is_nearest",
        }
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise AccessInputError("Access CSV is missing required serving-table columns.")

        rows: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str, str, str]] = set()
        for row_number, source in enumerate(reader, start=2):
            if source.get("access_group") != access_group or source.get("access_status") != "available":
                continue
            if allowed_pairs is not None and (source.get("complex_id"), source.get("feature_id")) not in allowed_pairs:
                continue
            key = tuple((source.get(column) or "").strip() for column in (
                "complex_id", "feature_id", "access_group", "main_origin_id", "calculation_version",
            ))
            if not all(key):
                raise AccessInputError(f"Row {row_number}: serving-table key cannot be blank.")
            if key in seen:
                raise AccessInputError(f"Row {row_number}: duplicate serving-table key {key!r}.")
            seen.add(key)
            walk_distance = optional_number(source.get("walk_distance_m"), field="walk_distance_m", row_number=row_number)
            walk_time = optional_number(source.get("walk_time_min"), field="walk_time_min", row_number=row_number)
            if walk_distance is None or walk_time is None:
                raise AccessInputError(f"Row {row_number}: available access must have distance and time.")
            if max_walk_distance_m is not None and walk_distance >= max_walk_distance_m:
                continue
            rows.append(
                {
                    "complex_id": key[0],
                    "feature_id": key[1],
                    "access_group": key[2],
                    "main_origin_id": key[3],
                    "origin_method": (source.get("origin_method") or "").strip(),
                    "calculation_version": key[4],
                    "policy_version": (source.get("policy_version") or "").strip() or None,
                    "reference_date": (source.get("reference_date") or "").strip() or None,
                    "straight_distance_m": optional_number(source.get("straight_distance_m"), field="straight_distance_m", row_number=row_number),
                    "walk_distance_m": walk_distance,
                    "walk_time_min": walk_time,
                    "distance_method": (source.get("distance_method") or "").strip(),
                    "access_status": "available",
                    "category_distance_limit_m": optional_number(source.get("category_distance_limit_m"), field="category_distance_limit_m", row_number=row_number),
                    "is_nearest": parse_bool(source.get("is_nearest"), field="is_nearest", row_number=row_number),
                    "selection_reason": (source.get("selection_reason") or "").strip() or None,
                    "failure_reason": None,
                    "qa_flags": parse_flags(source.get("qa_flags")),
                }
            )
    if not rows:
        raise AccessInputError(f"No available {access_group} rows found in {path}.")
    return rows


def chunks(values: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for offset in range(0, len(values), size):
        yield values[offset : offset + size]


def upsert_rows(rows: list[dict[str, Any]], *, batch_size: int) -> None:
    supabase_url = configured_value("SUPABASE_URL")
    service_role_key = configured_value("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required with --apply.")
    url = supabase_url.rstrip("/") + "/rest/v1/complex_feature_access"
    headers = {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    request_url = f"{url}?{urlencode({'on_conflict': UPSERT_COLUMNS})}"
    for batch in chunks(rows, batch_size):
        request = Request(
            request_url,
            data=json.dumps(batch, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=60) as response:
                if not 200 <= response.status < 300:
                    raise RuntimeError(f"Supabase access upsert failed with HTTP {response.status}.")
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"Supabase access upsert failed with HTTP {exc.code}: {details}") from exc
        except URLError as exc:
            raise RuntimeError("Supabase access upsert could not reach the configured project.") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load compact complex-to-facility access facts.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--access-group", default="medical_clinic")
    parser.add_argument(
        "--max-walk-distance-m",
        type=float,
        help="Keep only routes below this distance, matching an existing display cutoff.",
    )
    parser.add_argument(
        "--route-backup",
        type=Path,
        help="Restrict rows to the previously backed-up medical route keys, preserving FK-safe hospital coverage.",
    )
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--apply", action="store_true", help="Write to Supabase. Omit for validation-only dry run.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.batch_size <= 1_000:
        raise AccessInputError("batch_size must be between 1 and 1000.")
    if args.max_walk_distance_m is not None and args.max_walk_distance_m <= 0:
        raise AccessInputError("max_walk_distance_m must be positive.")
    allowed_pairs = allowed_pairs_from_route_backup(args.route_backup) if args.route_backup else None
    rows = read_rows(
        args.input,
        access_group=args.access_group,
        max_walk_distance_m=args.max_walk_distance_m,
        allowed_pairs=allowed_pairs,
    )
    if args.apply:
        upsert_rows(rows, batch_size=args.batch_size)
    print(json.dumps({"status": "APPLIED" if args.apply else "DRY_RUN", "accessGroup": args.access_group, "rowCount": len(rows), "input": str(args.input)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
