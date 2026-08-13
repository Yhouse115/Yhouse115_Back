from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from app.api.routes.environment import get_environment_service
from app.main import app
from app.schemas.environment import (
    AdminDong,
    ApiMeta,
    AxisStatus,
    AxisSummary,
    ComplexEnvironmentResponse,
    ComplexListResponse,
    ComplexMarker,
    EnvironmentAxis,
    EnvironmentFeature,
    EnvironmentFeaturesResponse,
    Position,
    SourceReference,
)
from app.services.environment import AXIS_BY_KEY, EnvironmentNotFoundError, EnvironmentService


def meta() -> ApiMeta:
    return ApiMeta(
        request_id=UUID("00000000-0000-0000-0000-000000000001"),
        schema_version="1.0.0",
        generated_at=datetime(2026, 8, 13, tzinfo=UTC),
        calculation_version="test-calculation-v1",
        policy_version="test-policy-v1",
    )


class FakeEnvironmentService:
    def __init__(self, *, known_complex: bool = True) -> None:
        self.known_complex = known_complex
        self.feature_requests: list[tuple[str, EnvironmentAxis, int]] = []

    async def list_complexes(self, district: str, limit: int) -> ComplexListResponse:
        assert district == "yangcheon"
        return ComplexListResponse(
            meta=meta(),
            items=[
                ComplexMarker(
                    apartment_complex_id="CX-001",
                    name="목동센트럴푸르지오",
                    admin_dong=AdminDong(code="1147051000", name="목1동"),
                    position=Position(latitude=37.5237051, longitude=126.8766956),
                    household_count=248,
                    approval_date="2015-06-30",
                )
            ][:limit],
        )

    async def get_environment(self, complex_id: str) -> ComplexEnvironmentResponse:
        if not self.known_complex:
            raise EnvironmentNotFoundError(complex_id)
        summaries = [
            AxisSummary(
                axis=axis,
                label=label,
                status=AxisStatus.AVAILABLE,
            )
            for axis, label in (
                (EnvironmentAxis.TRANSPORT, "교통"),
                (EnvironmentAxis.PARKS_PLAY, "공원·놀이"),
                (EnvironmentAxis.MEDICAL, "의료·약국"),
                (EnvironmentAxis.EDUCATION_CARE, "교육·돌봄"),
                (EnvironmentAxis.CONVENIENCE, "생활편의"),
            )
        ]
        return ComplexEnvironmentResponse(meta=meta(), apartment_complex_id=complex_id, summary=summaries)

    async def get_axis_features(
        self,
        complex_id: str,
        axis: EnvironmentAxis,
        limit: int,
    ) -> EnvironmentFeaturesResponse:
        if not self.known_complex:
            raise EnvironmentNotFoundError(complex_id)
        self.feature_requests.append((complex_id, axis, limit))
        source = SourceReference(
            dataset_id="healthcare_pediatrics_yangcheon",
            source_name="양천구 소아청소년과",
            reference_date="2026-07-31",
        )
        items = (
            [
                EnvironmentFeature(
                    feature_id="pediatrics:1",
                    axis=axis,
                    feature_type="pediatrics",
                    name="오목교소아청소년과",
                    address="서울 양천구 목동동로 1",
                    position=Position(latitude=37.524, longitude=126.876),
                    walk_distance_meters=420,
                    walk_time_minutes=6.3,
                    distance_method="walking_network",
                    access_status="available",
                    source=source,
                )
            ]
            if axis == EnvironmentAxis.MEDICAL
            else []
        )
        return EnvironmentFeaturesResponse(
            meta=meta(),
            apartment_complex_id=complex_id,
            axis=axis,
            status=AxisStatus.AVAILABLE,
            total_count=len(items),
            items=items,
        )


def client_for(service: FakeEnvironmentService) -> TestClient:
    app.dependency_overrides[get_environment_service] = lambda: service
    return TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_list_map_complexes_exposes_stable_marker_contract() -> None:
    response = client_for(FakeEnvironmentService()).get("/api/v1/map/complexes?district=yangcheon")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["schemaVersion"] == "1.0.0"
    assert body["items"] == [
        {
            "apartmentComplexId": "CX-001",
            "name": "목동센트럴푸르지오",
            "adminDong": {"code": "1147051000", "name": "목1동"},
            "position": {"latitude": 37.5237051, "longitude": 126.8766956},
            "householdCount": 248,
            "approvalDate": "2015-06-30",
        }
    ]


def test_environment_summary_always_returns_five_axes_in_display_order() -> None:
    response = client_for(FakeEnvironmentService()).get("/api/v1/complexes/CX-001/environment")

    assert response.status_code == 200
    summary = response.json()["summary"]
    assert [item["axis"] for item in summary] == [
        "transport",
        "parks_play",
        "medical",
        "education_care",
        "convenience",
    ]
    assert summary[-1]["status"] == "available"


def test_axis_features_passes_axis_and_limit_without_combining_axes() -> None:
    service = FakeEnvironmentService()

    response = client_for(service).get("/api/v1/complexes/CX-001/environment/features?axis=medical&limit=20")

    assert response.status_code == 200
    assert service.feature_requests == [("CX-001", EnvironmentAxis.MEDICAL, 20)]
    body = response.json()
    assert body["axis"] == "medical"
    assert body["items"][0]["walkDistanceMeters"] == 420
    assert body["items"][0]["source"]["referenceDate"] == "2026-07-31"


def test_invalid_district_uses_stable_error_shape() -> None:
    response = client_for(FakeEnvironmentService()).get("/api/v1/map/complexes?district=gangseo")

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "UNSUPPORTED_DISTRICT"
    assert body["details"] == [{"field": "district", "reason": "unsupported_value"}]


def test_unknown_complex_returns_not_found() -> None:
    response = client_for(FakeEnvironmentService(known_complex=False)).get("/api/v1/complexes/CX-MISSING/environment")

    assert response.status_code == 404
    assert response.json()["code"] == "COMPLEX_NOT_FOUND"


def test_medical_headline_uses_precomputed_walk_facts() -> None:
    service = EnvironmentService(repository=object())

    summary = service._build_axis_summary(
        AXIS_BY_KEY[EnvironmentAxis.MEDICAL],
        [
            {
                "access_group": "pediatrics",
                "summary_status": "available",
                "nearest_feature_id": "pediatrics:1",
                "nearest_feature_type": "pediatrics",
                "nearest_feature_name": "오목교소아청소년과",
                "nearest_walk_distance_m": 420.4,
                "nearest_walk_time_min": 6.3,
                "count_within_5min": 1,
                "count_within_10min": 2,
                "count_within_15min": 3,
                "selected_feature_count": 3,
                "metrics": {},
                "qa_flags": [],
            }
        ],
    )

    assert summary.headline == "도보 10분 이내 소아과 2곳 · 가장 가까운 곳 420m"


def test_convenience_headline_uses_precomputed_500m_count_and_mart() -> None:
    service = EnvironmentService(repository=object())
    summary = service._build_axis_summary(
        AXIS_BY_KEY[EnvironmentAxis.CONVENIENCE],
        [
            {
                "access_group": "daily_convenience",
                "summary_status": "available",
                "nearest_feature_id": "commercial:1",
                "nearest_feature_type": "daily_commerce",
                "nearest_feature_name": "생활상점",
                "nearest_walk_distance_m": 85.0,
                "nearest_walk_time_min": 1.2,
                "count_within_5min": 12,
                "count_within_10min": 40,
                "count_within_15min": 80,
                "selected_feature_count": 12,
                "metrics": {
                    "convenienceCountWithin500WalkMeters": 12,
                    "nearestMartName": "양천마트",
                    "nearestMartWalkDistanceMeters": 420.2,
                },
                "qa_flags": [],
            }
        ],
    )

    assert summary.status == AxisStatus.AVAILABLE
    assert summary.headline == "보행 500m 이내 편의시설 12곳 · 최근접 마트 양천마트 420m"
