from typing import Dict, List
from pydantic import BaseModel


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
    counts: Dict[str, Dict[str, int]]  # { "TRADE": { "APT": 61, ... }, "JEONSE": { ... } }


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
