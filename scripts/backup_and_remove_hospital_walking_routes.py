"""Back up and remove stored hospital route geometries from Supabase.

The default invocation is a dry run.  ``--apply`` exports all matching route
rows to a local JSON backup, verifies the exported count, then deletes exactly
that access group.  It never deletes hospital facilities or access summaries.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from load_complex_feature_walking_routes import configured_value

WORKSPACE = Path(__file__).resolve().parents[4]
DEFAULT_BACKUP_DIR = WORKSPACE / "data" / "local-backups" / "walking-routes"
ACCESS_GROUP = "medical_clinic"
PAGE_SIZE = 1_000


def configured_api() -> tuple[str, dict[str, str]]:
    supabase_url = configured_value("SUPABASE_URL")
    service_role_key = configured_value("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required.")
    return (
        supabase_url.rstrip("/") + "/rest/v1/complex_feature_walking_route",
        {
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Content-Type": "application/json",
        },
    )


def request_json(url: str, headers: dict[str, str], params: dict[str, str]) -> list[dict[str, Any]]:
    request_url = f"{url}?{urlencode(params)}"
    request = Request(request_url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"Hospital route backup query failed with HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}") from exc
    except URLError as exc:
        raise RuntimeError("Hospital route backup query could not reach the configured project.") from exc
    if not isinstance(payload, list):
        raise RuntimeError("Hospital route backup query returned an unexpected response.")
    return [dict(row) for row in payload]


def fetch_all_hospital_routes(url: str, headers: dict[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = request_json(
            url,
            headers,
            {
                "select": "*",
                "access_group": f"eq.{ACCESS_GROUP}",
                "order": "complex_id,feature_id,main_origin_id,calculation_version",
                "limit": str(PAGE_SIZE),
                "offset": str(offset),
            },
        )
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE


def delete_hospital_routes(url: str, headers: dict[str, str], expected_count: int) -> int:
    params = {"access_group": f"eq.{ACCESS_GROUP}"}
    request_url = f"{url}?{urlencode(params)}"
    # Returning every deleted JSONB geometry would needlessly transfer the
    # entire backup again.  The caller verifies that the filtered table is
    # empty afterwards, while the backup above remains the recovery copy.
    delete_headers = {**headers, "Prefer": "return=minimal"}
    request = Request(request_url, headers=delete_headers, method="DELETE")
    try:
        with urlopen(request, timeout=120) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(f"Hospital route delete failed with HTTP {response.status}.")
    except HTTPError as exc:
        raise RuntimeError(f"Hospital route delete failed with HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}") from exc
    except URLError as exc:
        raise RuntimeError("Hospital route delete could not reach the configured project.") from exc
    if fetch_all_hospital_routes(url, headers):
        raise RuntimeError("Hospital route delete did not remove every medical_clinic route row.")
    return expected_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Back up and delete stored hospital walking routes only.")
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    parser.add_argument("--apply", action="store_true", help="Write a backup then delete hospital route rows.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    url, headers = configured_api()
    rows = fetch_all_hospital_routes(url, headers)
    result: dict[str, Any] = {"status": "DRY_RUN", "accessGroup": ACCESS_GROUP, "routeRowCount": len(rows)}
    if args.apply:
        args.backup_dir.mkdir(parents=True, exist_ok=True)
        backup = args.backup_dir / f"hospital_walking_routes_{datetime.now().strftime('%Y%m%dT%H%M%S')}.json"
        backup.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        if not backup.is_file() or backup.stat().st_size == 0:
            raise RuntimeError("Hospital route backup was not created.")
        deleted_count = delete_hospital_routes(url, headers, len(rows))
        result = {
            "status": "APPLIED",
            "accessGroup": ACCESS_GROUP,
            "routeRowCount": len(rows),
            "deletedRowCount": deleted_count,
            "backup": str(backup),
            "backupBytes": backup.stat().st_size,
        }
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
