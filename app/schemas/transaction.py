from typing import List
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
