from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class DependencyStatus(BaseModel):
    database_configured: bool
    database_connected: Optional[bool] = None
    supabase_configured: bool
    supabase_admin_configured: bool
    naver_maps_configured: bool


class RuntimeConfigResponse(BaseModel):
    environment: str
    api_prefix: str
    cors_origins: List[str]
    dependencies: DependencyStatus
