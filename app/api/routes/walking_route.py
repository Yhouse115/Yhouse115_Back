from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.schemas.environment import ApiErrorResponse
from app.schemas.walking_route import WalkingRouteResponse
from app.services.walking_route import (
    WalkingRouteDataError,
    WalkingRouteNotFoundError,
    WalkingRouteService,
)

router = APIRouter(tags=["walking-route"])


def get_walking_route_service() -> WalkingRouteService:
    return WalkingRouteService()


def walking_route_error(status_code: int, code: str, message: str) -> JSONResponse:
    body = ApiErrorResponse(request_id=uuid4(), code=code, message=message)
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json", by_alias=True))


@router.get(
    "/complexes/{complex_id}/features/{feature_id}/walking-route",
    response_model=WalkingRouteResponse,
    responses={404: {"model": ApiErrorResponse}, 503: {"model": ApiErrorResponse}},
)
async def get_walking_route(
    complex_id: str,
    feature_id: str,
    service: WalkingRouteService = Depends(get_walking_route_service),
) -> WalkingRouteResponse | JSONResponse:
    """Return one stored facility route. This endpoint never routes on request."""
    try:
        return await service.get_walking_route(complex_id=complex_id, feature_id=feature_id)
    except WalkingRouteNotFoundError:
        return walking_route_error(
            404,
            "WALKING_ROUTE_NOT_FOUND",
            "No pre-computed walking route is available for this apartment and facility.",
        )
    except (WalkingRouteDataError, RuntimeError):
        return walking_route_error(
            503,
            "WALKING_ROUTE_DATA_UNAVAILABLE",
            "The stored walking route is temporarily unavailable.",
        )
