from typing import Dict, List, Optional
from pydantic import BaseModel


# Standard Pagination Schema
class PaginationDTO(BaseModel):
    page: int
    size: int
    totalElements: int
    totalPages: int
    hasNext: bool
    hasPrevious: bool


# --- API #1: Inventory Summary (/summary/inventory) ---
class InventoryItemDTO(BaseModel):
    house_type: str
    count: int


class InventorySummaryResponse(BaseModel):
    admin_dong_code: str
    admin_dong_name: str
    total_stock_count: int
    items: List[InventoryItemDTO]


# --- API #2: Transaction Count (/summary/transaction-count) ---
class MonthlyTransactionSeriesItem(BaseModel):
    yearMonth: str
    totalCount: int
    counts: Dict[str, Dict[str, int]]


class TransactionCountData(BaseModel):
    adminDongCode: str
    adminDongName: str
    periodStart: str
    periodEnd: str
    transactionTypes: List[str]
    buildingTypes: List[str]
    series: List[MonthlyTransactionSeriesItem]


class TransactionCountResponse(BaseModel):
    status: int = 200
    message: str = "SUCCESS"
    data: TransactionCountData


# --- API #3: Trade List (/transactions/trades) ---
class TradeItemDTO(BaseModel):
    tradeId: str
    pnu: Optional[str] = None
    dealDate: Optional[str] = None
    buildingType: Optional[str] = None
    aptName: Optional[str] = None
    adminDongCode: Optional[str] = None
    adminDongName: Optional[str] = None
    legalDongCode: Optional[str] = None
    legalDongName: Optional[str] = None
    jibunAddress: Optional[str] = None
    jibun: Optional[str] = None
    floor: Optional[int] = None
    exclArea: Optional[float] = None
    dealAmount: Optional[int] = None
    pricePerM2: Optional[float] = None
    buildYear: Optional[int] = None
    cancelDealDay: Optional[str] = None


class TradeListData(BaseModel):
    pagination: PaginationDTO
    items: List[TradeItemDTO]


class TradeListResponse(BaseModel):
    status: int = 200
    message: str = "SUCCESS"
    data: TradeListData
