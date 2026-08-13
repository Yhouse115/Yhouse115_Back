from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import httpx

from app.core.config import settings


class EnvironmentRepository:
    """Read API-ready environment data from the five Supabase serving tables."""

    def __init__(self) -> None:
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for the environment API.")
        self.base_url = settings.supabase_url.rstrip("/") + "/rest/v1/"
        self.headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
        }

    async def _get(self, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(self.base_url + table, params=params, headers=self.headers)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Environment table query failed: {table}") from exc
        payload = response.json()
        if not isinstance(payload, list):
            raise RuntimeError(f"Unexpected environment table response: {table}")
        return [dict(row) for row in payload]

    async def _get_all(self, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for offset in range(0, 100_000, 1_000):
            batch = await self._get(table, {**params, "limit": "1000", "offset": str(offset)})
            rows.extend(batch)
            if len(batch) < 1_000:
                return rows
        raise RuntimeError(f"Environment table page limit exceeded: {table}")

    @staticmethod
    def _in_filter(values: Iterable[str]) -> str:
        # Serving IDs do not contain commas or parentheses. Rejecting them
        # here avoids turning a value into a PostgREST filter expression.
        normalized = [str(value) for value in values]
        if any(not value or any(character in value for character in ",()") for value in normalized):
            raise RuntimeError("Invalid serving-table identifier")
        return "in.(" + ",".join(normalized) + ")"

    async def list_complexes(self, district: str, limit: int) -> list[dict[str, Any]]:
        if district != "yangcheon":
            return []
        return await self._get(
            "apartment_complex",
            {
                "select": "complex_id,name,admin_dong_code,admin_dong_name,latitude,longitude,household_count,approval_date",
                "admin_dong_code": "like.11470*",
                "order": "household_count.desc.nullslast,name,complex_id",
                "limit": str(limit),
            },
        )

    async def get_complex(self, complex_id: str) -> dict[str, Any] | None:
        rows = await self._get(
            "apartment_complex",
            {
                "select": "complex_id,name,admin_dong_code,admin_dong_name,latitude,longitude",
                "complex_id": f"eq.{complex_id}",
                "limit": "1",
            },
        )
        return rows[0] if rows else None

    async def get_summaries(self, complex_id: str) -> list[dict[str, Any]]:
        raw_rows = await self._get_all(
            "complex_environment_summary",
            {
                "select": "complex_id,access_group,main_origin_id,origin_method,calculation_version,policy_version,reference_date,category_distance_limit_m,nearest_feature_id,nearest_walk_distance_m,nearest_walk_time_min,count_within_5min,count_within_10min,count_within_15min,selected_feature_count,metrics,summary_status,failure_reason,qa_flags,loaded_at",
                "complex_id": f"eq.{complex_id}",
                "order": "access_group,reference_date.desc.nullslast,loaded_at.desc",
            },
        )
        latest: dict[str, dict[str, Any]] = {}
        for row in raw_rows:
            latest.setdefault(str(row["access_group"]), row)
        rows = list(latest.values())
        feature_ids = [str(row["nearest_feature_id"]) for row in rows if row.get("nearest_feature_id")]
        if not feature_ids:
            return rows
        features = await self._get_all(
            "environment_feature",
            {
                "select": "feature_id,feature_type,name,source_dataset_id",
                "feature_id": self._in_filter(feature_ids),
            },
        )
        by_feature = {str(row["feature_id"]): row for row in features}
        source_ids = sorted({str(row["source_dataset_id"]) for row in features})
        datasets = await self._get_all(
            "source_dataset",
            {
                "select": "source_dataset_id,source_name,reference_date",
                "source_dataset_id": self._in_filter(source_ids),
            },
        ) if source_ids else []
        by_dataset = {str(row["source_dataset_id"]): row for row in datasets}
        for row in rows:
            feature = by_feature.get(str(row.get("nearest_feature_id")))
            if not feature:
                continue
            dataset = by_dataset.get(str(feature["source_dataset_id"]))
            row.update(
                {
                    "nearest_feature_type": feature.get("feature_type"),
                    "nearest_feature_name": feature.get("name"),
                    "nearest_source_dataset_id": feature.get("source_dataset_id"),
                    "nearest_source_name": dataset.get("source_name") if dataset else None,
                    "nearest_source_reference_date": dataset.get("reference_date") if dataset else None,
                }
            )
        return sorted(rows, key=lambda row: str(row["access_group"]))

    async def list_axis_features(
        self,
        complex_id: str,
        access_groups: Iterable[str],
        limit: int,
    ) -> tuple[int, list[dict[str, Any]]]:
        groups = list(access_groups)
        raw_rows = await self._get_all(
            "complex_feature_access",
            {
                "select": "complex_id,feature_id,access_group,main_origin_id,calculation_version,reference_date,walk_distance_m,walk_time_min,distance_method,access_status,qa_flags,loaded_at",
                "complex_id": f"eq.{complex_id}",
                "access_group": self._in_filter(groups),
                "order": "feature_id,access_group,reference_date.desc.nullslast,loaded_at.desc",
            },
        )
        latest: dict[tuple[str, str], dict[str, Any]] = {}
        for row in raw_rows:
            latest.setdefault((str(row["feature_id"]), str(row["access_group"])), row)
        deduplicated: dict[str, dict[str, Any]] = {}
        for row in latest.values():
            feature_id = str(row["feature_id"])
            existing = deduplicated.get(feature_id)
            rank = (
                row.get("walk_time_min") is None,
                float(row["walk_time_min"] or float("inf")),
                float(row["walk_distance_m"] or float("inf")),
                str(row["access_group"]),
            )
            if existing is None or rank < (
                existing.get("walk_time_min") is None,
                float(existing["walk_time_min"] or float("inf")),
                float(existing["walk_distance_m"] or float("inf")),
                str(existing["access_group"]),
            ):
                deduplicated[feature_id] = row
        selected_access = list(deduplicated.values())
        if not selected_access:
            return 0, []
        features = await self._get_all(
            "environment_feature",
            {
                "select": "feature_id,feature_type,name,address,latitude,longitude,attributes,source_dataset_id",
                "feature_id": self._in_filter(row["feature_id"] for row in selected_access),
            },
        )
        by_feature = {str(row["feature_id"]): row for row in features}
        source_ids = sorted({str(row["source_dataset_id"]) for row in features})
        datasets = await self._get_all(
            "source_dataset",
            {
                "select": "source_dataset_id,source_name,reference_date",
                "source_dataset_id": self._in_filter(source_ids),
            },
        ) if source_ids else []
        by_dataset = {str(row["source_dataset_id"]): row for row in datasets}
        records: list[dict[str, Any]] = []
        for access in selected_access:
            feature = by_feature.get(str(access["feature_id"]))
            if not feature:
                continue
            dataset = by_dataset.get(str(feature["source_dataset_id"]))
            if not dataset:
                continue
            records.append(
                {
                    **access,
                    "feature_type": feature["feature_type"],
                    "name": feature.get("name"),
                    "address": feature.get("address"),
                    "latitude": feature["latitude"],
                    "longitude": feature["longitude"],
                    "attributes": feature.get("attributes") or {},
                    "source_dataset_id": feature["source_dataset_id"],
                    "source_name": dataset["source_name"],
                    "source_reference_date": dataset.get("reference_date"),
                }
            )
        records.sort(
            key=lambda row: (
                row.get("walk_time_min") is None,
                float(row["walk_time_min"] or float("inf")),
                float(row["walk_distance_m"] or float("inf")),
                str(row["feature_id"]),
            )
        )
        return len(records), records[:limit]
