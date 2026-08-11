from dataclasses import dataclass

from app.core.config import settings


@dataclass(frozen=True)
class NaverMapsConfig:
    client_id: str
    client_secret: str
    geocode_base_url: str

    @property
    def geocode_headers(self) -> dict[str, str]:
        return {
            "x-ncp-apigw-api-key-id": self.client_id,
            "x-ncp-apigw-api-key": self.client_secret,
        }


def get_naver_maps_config() -> NaverMapsConfig:
    if not settings.naver_maps_client_id or not settings.naver_maps_client_secret:
        raise RuntimeError("NAVER_MAPS_CLIENT_ID and NAVER_MAPS_CLIENT_SECRET are required.")

    return NaverMapsConfig(
        client_id=settings.naver_maps_client_id,
        client_secret=settings.naver_maps_client_secret,
        geocode_base_url=settings.naver_maps_geocode_base_url,
    )
