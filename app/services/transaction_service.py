import asyncpg
from app.repositories.transaction_repository import (
    TransactionRepository,
    normalize_building_type_code,
)
from app.schemas.transaction import (
    InventoryItemDTO,
    InventorySummaryResponse,
)


class TransactionService:

    @classmethod
    async def get_inventory_summary(
        cls,
        conn: asyncpg.Connection,
        admin_dong_code: str
    ) -> InventorySummaryResponse:
        admin_info = await TransactionRepository.get_admin_dong_info(conn, admin_dong_code)
        dong_name = admin_info["admin_dong_name"] if admin_info else "미분류"

        rows = await TransactionRepository.get_housing_stock_counts(conn, admin_dong_code)

        counts_map = {"APT": 0, "TOWNHOUSE": 0, "OFFICETEL": 0}
        for r in rows:
            code = normalize_building_type_code(r.get("house_type"))
            if code in counts_map:
                counts_map[code] += r.get("count", 0)

        total_stock = sum(counts_map.values())
        items = [
            InventoryItemDTO(house_type="APT", count=counts_map["APT"]),
            InventoryItemDTO(house_type="TOWNHOUSE", count=counts_map["TOWNHOUSE"]),
            InventoryItemDTO(house_type="OFFICETEL", count=counts_map["OFFICETEL"])
        ]

        return InventorySummaryResponse(
            admin_dong_code=admin_dong_code,
            admin_dong_name=dong_name,
            total_stock_count=total_stock,
            items=items
        )
