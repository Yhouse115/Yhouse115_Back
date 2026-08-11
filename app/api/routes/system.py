from __future__ import annotations

from typing import Optional

from fastapi import APIRouter

from app.core.config import settings
from app.db.postgres import check_database_connection
from app.schemas.system import DependencyStatus, RuntimeConfigResponse

router = APIRouter(prefix="/system", tags=["system"])


def build_dependency_status(database_connected: Optional[bool] = None) -> DependencyStatus:
    return DependencyStatus(
        database_configured=settings.is_database_configured,
        database_connected=database_connected,
        supabase_configured=settings.is_supabase_configured,
        supabase_admin_configured=settings.is_supabase_admin_configured,
        naver_maps_configured=settings.is_naver_maps_configured,
    )


@router.get("/config", response_model=RuntimeConfigResponse)
def runtime_config() -> RuntimeConfigResponse:
    return RuntimeConfigResponse(
        environment=settings.app_env,
        api_prefix=settings.api_prefix,
        cors_origins=settings.parsed_cors_origins,
        dependencies=build_dependency_status(),
    )


@router.get("/dependencies", response_model=DependencyStatus)
async def dependency_status() -> DependencyStatus:
    database_connected = None
    if settings.is_database_configured:
        try:
            database_connected = await check_database_connection()
        except Exception:
            database_connected = False

    return build_dependency_status(database_connected=database_connected)
