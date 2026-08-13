from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.walking_route import get_walking_route_service, router
from app.schemas.walking_route import WalkingRouteResponse
from app.services.walking_route import (
    WalkingRouteDataError,
    WalkingRouteNotFoundError,
    WalkingRouteService,
    route_coordinates_from_value,
)


class FakeWalkingRouteService:
    def __init__(self, *, result: str = "available") -> None:
        self.result = result
        self.requests: list[tuple[str, str]] = []

    async def get_walking_route(self, *, complex_id: str, feature_id: str) -> WalkingRouteResponse:
        self.requests.append((complex_id, feature_id))
        if self.result == "missing":
            raise WalkingRouteNotFoundError()
        if self.result == "invalid":
            raise WalkingRouteDataError()
        return WalkingRouteResponse(
            complex_id=complex_id,
            feature_id=feature_id,
            access_group="childcare" if feature_id.startswith("education_childcare_") else "elementary_school",
            route_coordinates=[(126.8747857, 37.5198083), (126.8744162, 37.5195816)],
            walk_distance_meters=532.4,
            walk_time_minutes=7.61,
            route_method="oa21208_dijkstra_geodesic_link_length_plus_snap_legs",
            calculated_at=datetime(2026, 8, 13, 16, 35, 43, tzinfo=UTC),
        )


class FakeWalkingRouteRepository:
    def __init__(self, row: dict[str, object] | None) -> None:
        self.row = row
        self.requests: list[dict[str, str]] = []

    async def get_latest_route(self, **kwargs: str) -> dict[str, object] | None:
        self.requests.append(kwargs)
        return self.row


app = FastAPI()
app.include_router(router, prefix="/api/v1")


def client_for(service: FakeWalkingRouteService) -> TestClient:
    app.dependency_overrides[get_walking_route_service] = lambda: service
    return TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_get_walking_route_returns_render_ready_stored_coordinates() -> None:
    service = FakeWalkingRouteService()

    response = client_for(service).get(
        "/api/v1/complexes/CX-004A0B56AB68/features/education_elementary_yangcheon:7081453/walking-route"
    )

    assert response.status_code == 200
    assert service.requests == [("CX-004A0B56AB68", "education_elementary_yangcheon:7081453")]
    assert response.json() == {
        "complexId": "CX-004A0B56AB68",
        "featureId": "education_elementary_yangcheon:7081453",
        "accessGroup": "elementary_school",
        "routeCoordinates": [[126.8747857, 37.5198083], [126.8744162, 37.5195816]],
        "walkDistanceMeters": 532.4,
        "walkTimeMinutes": 7.61,
        "routeMethod": "oa21208_dijkstra_geodesic_link_length_plus_snap_legs",
        "calculatedAt": "2026-08-13T16:35:43Z",
    }


def test_get_walking_route_returns_404_when_pair_was_not_precomputed() -> None:
    response = client_for(FakeWalkingRouteService(result="missing")).get(
        "/api/v1/complexes/CX-001/features/education_elementary_yangcheon:missing/walking-route"
    )

    assert response.status_code == 404
    assert response.json()["code"] == "WALKING_ROUTE_NOT_FOUND"


def test_get_walking_route_accepts_a_precomputed_childcare_route() -> None:
    service = FakeWalkingRouteService()

    response = client_for(service).get(
        "/api/v1/complexes/CX-001/features/education_childcare_yangcheon_20260731:row:1/walking-route"
    )

    assert response.status_code == 200
    assert response.json()["accessGroup"] == "childcare"


def test_get_walking_route_returns_503_for_invalid_stored_data() -> None:
    response = client_for(FakeWalkingRouteService(result="invalid")).get(
        "/api/v1/complexes/CX-001/features/education_elementary_yangcheon:bad/walking-route"
    )

    assert response.status_code == 503
    assert response.json()["code"] == "WALKING_ROUTE_DATA_UNAVAILABLE"


def test_service_maps_latest_precomputed_route_without_calculation() -> None:
    repository = FakeWalkingRouteRepository(
        {
            "complex_id": "CX-001",
            "feature_id": "education_elementary_yangcheon:7081453",
            "access_group": "elementary_school",
            "route_coordinates": "[[126.87, 37.52], [126.88, 37.53]]",
            "walk_distance_m": "910.2",
            "walk_time_min": "13.0",
            "route_method": "local_dijkstra",
            "calculated_at": "2026-08-13T16:35:43+09:00",
        }
    )

    route = __import__("asyncio").run(
        WalkingRouteService(repository=repository).get_walking_route(
            complex_id="CX-001", feature_id="education_elementary_yangcheon:7081453"
        )
    )

    assert repository.requests == [
        {
            "complex_id": "CX-001",
            "feature_id": "education_elementary_yangcheon:7081453",
            "main_origin_id": "complex_center",
        }
    ]
    assert route.route_coordinates == [(126.87, 37.52), (126.88, 37.53)]
    assert route.walk_distance_meters == 910.2


def test_coordinate_validation_rejects_wrong_geojson_position_order_or_shape() -> None:
    try:
        route_coordinates_from_value([[37.52, 126.87], [37.53, 126.88]])
    except WalkingRouteDataError as exc:
        assert "out-of-range" in str(exc)
    else:
        raise AssertionError("latitude/longitude positions should not be accepted as GeoJSON coordinates")
