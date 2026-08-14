import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.repositories.transaction_repository import TransactionRepository
from app.services.transaction_service import TransactionService


def test_resolves_kreb_legal_dong_jibun_address_to_pnu():
    rows = [{
        "pnu": "1147010200109010000",
        "property_name": "목동신시가지아파트",
        "legal_dong_name": "목동",
        "jibun": "901",
        "total_households": 1882,
    }]
    conn = AsyncMock()
    with patch.object(TransactionRepository, "resolve_building_pnu", new=AsyncMock(return_value=rows)) as resolver:
        result = asyncio.run(TransactionService.resolve_building_pnu(
            conn, "서울특별시 양천구 목동 901", 1882
        ))

    resolver.assert_awaited_once_with(conn, "목동", "901", 1882)
    assert result.data.pnu == "1147010200109010000"


def test_rejects_road_address_without_legal_dong_jibun():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(TransactionService.resolve_building_pnu(
            AsyncMock(), "서울특별시 양천구 목동서로 15", None
        ))

    assert exc.value.status_code == 422
