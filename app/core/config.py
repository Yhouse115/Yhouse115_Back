from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="WhyHouse Backend", alias="APP_NAME")
    app_env: str = Field(default="local", alias="APP_ENV")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    api_prefix: str = Field(default="/api/v1", alias="API_PREFIX")
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    database_url: Optional[str] = Field(default=None, alias="DATABASE_URL")
    supabase_url: Optional[str] = Field(default=None, alias="SUPABASE_URL")
    supabase_anon_key: Optional[str] = Field(default=None, alias="SUPABASE_ANON_KEY")
    supabase_service_role_key: Optional[str] = Field(
        default=None,
        alias="SUPABASE_SERVICE_ROLE_KEY",
    )

    naver_maps_client_id: Optional[str] = Field(
        default=None,
        alias="NAVER_MAPS_CLIENT_ID",
    )
    naver_maps_client_secret: Optional[str] = Field(
        default=None,
        alias="NAVER_MAPS_CLIENT_SECRET",
    )
    naver_maps_geocode_base_url: str = Field(
        default="https://naveropenapi.apigw.ntruss.com/map-geocode/v2",
        alias="NAVER_MAPS_GEOCODE_BASE_URL",
    )

    @property
    def parsed_cors_origins(self) -> List[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

    @property
    def is_database_configured(self) -> bool:
        return bool(self.database_url)

    @property
    def is_supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_anon_key)

    @property
    def is_supabase_admin_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key)

    @property
    def is_naver_maps_configured(self) -> bool:
        return bool(self.naver_maps_client_id and self.naver_maps_client_secret)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
