from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.schemas.environment import (
    ApiErrorDetail,
    ApiErrorResponse,
    ComplexEnvironmentResponse,
    ComplexListResponse,
    EnvironmentAxis,
    EnvironmentFeaturesResponse,
)
from app.services.environment import EnvironmentNotFoundError, EnvironmentService

router = APIRouter(tags=["environment"])


def get_environment_service() -> EnvironmentService:
    return EnvironmentService()


def api_error(
    status_code: int,
    code: str,
    message: str,
    *,
    field: str | None = None,
    reason: str | None = None,
) -> JSONResponse:
    details = [ApiErrorDetail(field=field, reason=reason)] if reason else []
    body = ApiErrorResponse(
        request_id=uuid4(),
        code=code,
        message=message,
        details=details,
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json", by_alias=True))


@router.get(
    "/map/complexes",
    response_model=ComplexListResponse,
    responses={422: {"model": ApiErrorResponse}, 503: {"model": ApiErrorResponse}},
)
async def list_map_complexes(
    district: str = Query(default="yangcheon", description="Current MVP district scope."),
    limit: int = Query(default=1000, ge=1, le=1000),
    service: EnvironmentService = Depends(get_environment_service),
) -> ComplexListResponse | JSONResponse:
    if district != "yangcheon":
        return api_error(
            422,
            "UNSUPPORTED_DISTRICT",
            "현재는 양천구 데이터만 조회할 수 있습니다.",
            field="district",
            reason="unsupported_value",
        )
    try:
        return await service.list_complexes(district=district, limit=limit)
    except RuntimeError:
        return api_error(503, "ENVIRONMENT_DATA_UNAVAILABLE", "생활환경 데이터를 준비 중입니다.")


@router.get(
    "/complexes/{apartment_complex_id}/environment",
    response_model=ComplexEnvironmentResponse,
    responses={404: {"model": ApiErrorResponse}, 503: {"model": ApiErrorResponse}},
)
async def get_complex_environment(
    apartment_complex_id: str,
    service: EnvironmentService = Depends(get_environment_service),
) -> ComplexEnvironmentResponse | JSONResponse:
    try:
        return await service.get_environment(apartment_complex_id)
    except EnvironmentNotFoundError:
        return api_error(404, "COMPLEX_NOT_FOUND", "요청한 단지를 찾을 수 없습니다.")
    except RuntimeError:
        return api_error(503, "ENVIRONMENT_DATA_UNAVAILABLE", "생활환경 데이터를 준비 중입니다.")


@router.get(
    "/complexes/{apartment_complex_id}/environment/features",
    response_model=EnvironmentFeaturesResponse,
    responses={404: {"model": ApiErrorResponse}, 503: {"model": ApiErrorResponse}},
)
async def get_complex_environment_features(
    apartment_complex_id: str,
    axis: EnvironmentAxis = Query(..., description="Environment axis to display."),
    limit: int = Query(default=20, ge=1, le=100),
    service: EnvironmentService = Depends(get_environment_service),
) -> EnvironmentFeaturesResponse | JSONResponse:
    try:
        return await service.get_axis_features(complex_id=apartment_complex_id, axis=axis, limit=limit)
    except EnvironmentNotFoundError:
        return api_error(404, "COMPLEX_NOT_FOUND", "요청한 단지를 찾을 수 없습니다.")
    except RuntimeError:
        return api_error(503, "ENVIRONMENT_DATA_UNAVAILABLE", "생활환경 데이터를 준비 중입니다.")
