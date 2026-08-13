import asyncpg
from fastapi import APIRouter, Depends, Query

from app.db.postgres import get_db_connection
from app.schemas.transaction import InventorySummaryResponse
from app.services.transaction_service import TransactionService

router = APIRouter(tags=["Transaction & Development APIs"])


@router.get("/summary/inventory", response_model=InventorySummaryResponse)
async def get_summary_inventory(
    admin_dong_code: str = Query(..., description="행정동 10자리 코드 (예: 1147051000)"),
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    return await TransactionService.get_inventory_summary(conn, admin_dong_code)
