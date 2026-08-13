from datetime import date
from typing import List, Optional
import asyncpg
from fastapi import APIRouter, Depends, Query

from app.db.postgres import get_db_connection
from app.schemas.transaction import (
    BuildingListResponse,
    BuildingUnitsResponse,
    DevelopmentListResponse,
    InventorySummaryResponse,
    RentListResponse,
    TradeListResponse,
    TransactionCountResponse,
)
from app.services.transaction_service import TransactionService

router = APIRouter(tags=["Transaction & Building & Development APIs"])


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


@router.get("/transactions/trades", response_model=TradeListResponse)
async def get_trades_list(
    admin_dong_code: Optional[str] = Query(None, description="관할 행정동 10자리 코드"),
    period_start: date = Query(..., description="조회 기간 시작일 (YYYY-MM-DD)"),
    period_end: date = Query(..., description="조회 기간 종료일 (YYYY-MM-DD)"),
    building_type: Optional[List[str]] = Query(None, description="건축물 유형 (APT, TOWNHOUSE, OFFICETEL, DETACHED)"),
    apt_name: Optional[str] = Query(None, description="단지명 / 건물명 검색어"),
    min_deal_amount: Optional[int] = Query(None, description="최소 매매가 (단위: 만원)"),
    max_deal_amount: Optional[int] = Query(None, description="최대 매매가 (단위: 만원)"),
    min_excl_area: Optional[float] = Query(None, description="최소 전용면적 (m²)"),
    max_excl_area: Optional[float] = Query(None, description="최대 전용면적 (m²)"),
    page: int = Query(1, ge=1, description="요청 페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지당 출력 건수"),
    sort: str = Query("deal_date,desc", description="정렬 조건"),
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    return await TransactionService.get_trades_list(
        conn, admin_dong_code, period_start, period_end, building_type, apt_name,
        min_deal_amount, max_deal_amount, min_excl_area, max_excl_area, page, size, sort
    )


@router.get("/transactions/rents", response_model=RentListResponse)
async def get_rents_list(
    admin_dong_code: Optional[str] = Query(None, description="관할 행정동 10자리 코드"),
    period_start: date = Query(..., description="조회 기간 시작일 (YYYY-MM-DD)"),
    period_end: date = Query(..., description="조회 기간 종료일 (YYYY-MM-DD)"),
    rent_type: Optional[str] = Query(None, description="임대 유형 (JEONSE, MONTHLY)"),
    building_type: Optional[List[str]] = Query(None, description="건축물 유형 (APT, TOWNHOUSE, OFFICETEL, DETACHED)"),
    apt_name: Optional[str] = Query(None, description="단지명 / 건물명 검색어"),
    min_deposit: Optional[int] = Query(None, description="최소 보증금 (단위: 만원)"),
    max_deposit: Optional[int] = Query(None, description="최대 보증금 (단위: 만원)"),
    min_monthly_rent: Optional[int] = Query(None, description="최소 월세금 (단위: 만원)"),
    max_monthly_rent: Optional[int] = Query(None, description="최대 월세금 (단위: 만원)"),
    min_excl_area: Optional[float] = Query(None, description="최소 전용면적 (m²)"),
    max_excl_area: Optional[float] = Query(None, description="최대 전용면적 (m²)"),
    page: int = Query(1, ge=1, description="요청 페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지당 출력 건수"),
    sort: str = Query("deal_date,desc", description="정렬 조건"),
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    return await TransactionService.get_rents_list(
        conn, admin_dong_code, period_start, period_end, rent_type, building_type, apt_name,
        min_deposit, max_deposit, min_monthly_rent, max_monthly_rent,
        min_excl_area, max_excl_area, page, size, sort
    )


@router.get("/developments", response_model=DevelopmentListResponse)
async def get_developments_list(
    admin_dong_code: Optional[str] = Query(None, description="관할 행정동 10자리 코드"),
    dev_type: Optional[str] = Query(None, description="정비사업 종류 (REDEVELOPMENT, RECONSTRUCTION)"),
    project_name: Optional[str] = Query(None, description="정비사업 구역명 검색어"),
    stage_code: Optional[str] = Query(None, description="특정 달성 단계 코드 (STAGE_1 ~ STAGE_6)"),
    is_completed: Optional[bool] = Query(None, description="사업 완료(준공·입주) 여부"),
    pnu: Optional[str] = Query(None, description="정비구역 대표 PNU 19자리"),
    page: int = Query(1, ge=1, description="요청 페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지당 출력 건수"),
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    return await TransactionService.get_developments_list(
        conn, admin_dong_code, dev_type, project_name, stage_code, is_completed, pnu, page, size
    )


@router.get("/buildings", response_model=BuildingListResponse)
async def get_buildings_list(
    admin_dong_code: Optional[str] = Query(None, description="행정동 10자리 코드"),
    building_type: Optional[List[str]] = Query(None, description="건축물 유형 (APT, TOWNHOUSE, OFFICETEL, DETACHED)"),
    building_name: Optional[str] = Query(None, description="건물명 / 단지명 검색어"),
    page: int = Query(1, ge=1, description="요청 페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지당 출력 건수"),
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    return await TransactionService.get_buildings_list(
        conn, admin_dong_code, building_type, building_name, page, size
    )


@router.get("/buildings/unit-types", response_model=BuildingUnitsResponse)
async def get_building_unit_types(
    pnu: Optional[str] = Query(None, description="건축물 PNU 19자리"),
    building_name: Optional[str] = Query(None, description="건물명 / 단지명 검색어"),
    admin_dong_code: Optional[str] = Query(None, description="행정동 10자리 코드"),
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    return await TransactionService.get_building_unit_types(
        conn, pnu, building_name, admin_dong_code
    )
