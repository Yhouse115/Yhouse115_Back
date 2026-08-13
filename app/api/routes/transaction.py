from datetime import date
from typing import List, Optional
import asyncpg
from fastapi import APIRouter, Depends, Query

from app.db.postgres import get_db_connection
from app.schemas.transaction import (
    InventorySummaryResponse,
    TransactionCountResponse,
)
from app.services.transaction_service import TransactionService

router = APIRouter(tags=["Transaction & Development APIs"])


@router.get("/summary/inventory", response_model=InventorySummaryResponse)
async def get_summary_inventory(
    admin_dong_code: str = Query(..., description="행정동 10자리 코드 (예: 1147051000)"),
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    return await TransactionService.get_inventory_summary(conn, admin_dong_code)


@router.get("/summary/transaction-count", response_model=TransactionCountResponse)
async def get_summary_transaction_count(
    admin_dong_code: str = Query(..., description="행정동 10자리 코드"),
    period_start: date = Query(..., description="조회 기간 시작일 (YYYY-MM-DD)"),
    period_end: date = Query(..., description="조회 기간 종료일 (YYYY-MM-DD)"),
    transaction_type: Optional[List[str]] = Query(None, description="거래 유형 (TRADE, RENT_ALL, JEONSE, MONTHLY)"),
    building_type: Optional[List[str]] = Query(None, description="건축물 유형 (APT, TOWNHOUSE, OFFICETEL)"),
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    return await TransactionService.get_transaction_counts(
        conn, admin_dong_code, period_start, period_end, transaction_type, building_type
    )
