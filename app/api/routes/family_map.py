from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.family_map import (
    ApartmentSearchResponse,
    BoundsFeaturesResponse,
    NearbyFeaturesResponse,
)
from app.services.family_map import FamilyMapService

router = APIRouter(prefix="/family-map", tags=["family-map"])


@router.get("/apartments", response_model=ApartmentSearchResponse)
async def search_apartments(
    q: Optional[str] = Query(default=None, description="Apartment name or address search term."),
    limit: int = Query(default=20, ge=1, le=1000),
) -> ApartmentSearchResponse:
    service = FamilyMapService()
    items = await service.search_apartments(q, limit)
    return ApartmentSearchResponse(items=items)


@router.get("/apartments/{complex_id}/nearby", response_model=NearbyFeaturesResponse)
async def nearby_features(
    complex_id: str,
    radius_m: int = Query(default=50, ge=1, le=3000),
    categories: Optional[str] = Query(default=None, description="Comma-separated categories."),
    limit_per_source: int = Query(default=1000, ge=1, le=5000),
) -> NearbyFeaturesResponse:
    service = FamilyMapService()
    try:
        return await service.get_nearby_features(
            complex_id=complex_id,
            radius_m=radius_m,
            categories=categories,
            limit_per_source=limit_per_source,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/features", response_model=BoundsFeaturesResponse)
async def features_in_bounds(
    sw_lat: float = Query(..., ge=33, le=39),
    sw_lng: float = Query(..., ge=124, le=132),
    ne_lat: float = Query(..., ge=33, le=39),
    ne_lng: float = Query(..., ge=124, le=132),
    categories: Optional[str] = Query(default=None, description="Comma-separated categories."),
    zoom: int = Query(default=15, ge=1, le=21),
    limit_per_source: int = Query(default=1000, ge=1, le=5000),
) -> BoundsFeaturesResponse:
    if sw_lat > ne_lat or sw_lng > ne_lng:
        raise HTTPException(status_code=422, detail="Invalid map bounds.")

    service = FamilyMapService()
    return await service.get_features_in_bounds(
        sw_lat=sw_lat,
        sw_lng=sw_lng,
        ne_lat=ne_lat,
        ne_lng=ne_lng,
        categories=categories,
        zoom=zoom,
        limit_per_source=limit_per_source,
    )
