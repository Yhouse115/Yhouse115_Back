from datetime import date
import math
from typing import Dict, List, Optional
import asyncpg
from app.repositories.transaction_repository import (
    TransactionRepository,
    normalize_building_type_code,
)
from app.schemas.transaction import (
    InventoryItemDTO,
    InventorySummaryResponse,
    MonthlyTransactionSeriesItem,
    PaginationDTO,
    TradeItemDTO,
    TradeListData,
    TradeListResponse,
    TransactionCountData,
    TransactionCountResponse,
)


def generate_year_month_sequence(start_date: date, end_date: date) -> List[str]:
    months = []
    cur_y, cur_m = start_date.year, start_date.month
    end_y, end_m = end_date.year, end_date.month

    while (cur_y < end_y) or (cur_y == end_y and cur_m <= end_m):
        months.append(f"{cur_y:04d}-{cur_m:02d}")
        cur_m += 1
        if cur_m > 12:
            cur_m = 1
            cur_y += 1
    return months


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

    @classmethod
    async def get_transaction_counts(
        cls,
        conn: asyncpg.Connection,
        admin_dong_code: str,
        period_start: date,
        period_end: date,
        raw_tx_types: Optional[List[str]],
        raw_bld_types: Optional[List[str]]
    ) -> TransactionCountResponse:
        admin_info = await TransactionRepository.get_admin_dong_info(conn, admin_dong_code)
        dong_name = admin_info["admin_dong_name"] if admin_info else "미분류"

        tx_types = []
        if raw_tx_types:
            for t in raw_tx_types:
                for sub in t.split(","):
                    sub_clean = sub.strip().upper()
                    if sub_clean and sub_clean not in tx_types:
                        tx_types.append(sub_clean)
        if not tx_types:
            tx_types = ["TRADE", "JEONSE", "MONTHLY"]

        bld_types = []
        if raw_bld_types:
            for b in raw_bld_types:
                for sub in b.split(","):
                    sub_clean = normalize_building_type_code(sub.strip())
                    if sub_clean and sub_clean not in bld_types:
                        bld_types.append(sub_clean)
        if not bld_types:
            bld_types = ["APT", "TOWNHOUSE", "OFFICETEL"]

        trade_rows, rent_rows = await TransactionRepository.get_monthly_transaction_counts(
            conn, admin_dong_code, period_start, period_end
        )

        ym_list = generate_year_month_sequence(period_start, period_end)
        series_map: Dict[str, Dict[str, Dict[str, int]]] = {
            ym: {t: {b: 0 for b in bld_types} for t in tx_types} for ym in ym_list
        }

        for r in trade_rows:
            ym = r.get("year_month")
            if ym in series_map and "TRADE" in tx_types:
                b_code = normalize_building_type_code(r.get("house_type"))
                if b_code in bld_types:
                    series_map[ym]["TRADE"][b_code] += r.get("count", 0)

        for r in rent_rows:
            ym = r.get("year_month")
            if ym in series_map:
                b_code = normalize_building_type_code(r.get("house_type"))
                if b_code in bld_types:
                    r_type = str(r.get("rent_type") or "").strip()
                    cat = "JEONSE" if r_type == "전세" else ("MONTHLY" if r_type == "월세" else None)
                    if cat and cat in tx_types:
                        series_map[ym][cat][b_code] += r.get("count", 0)
                    elif "RENT_ALL" in tx_types:
                        if "RENT_ALL" not in series_map[ym]:
                            series_map[ym]["RENT_ALL"] = {b: 0 for b in bld_types}
                        series_map[ym]["RENT_ALL"][b_code] += r.get("count", 0)

        series_items = []
        for ym in ym_list:
            counts_dict = series_map[ym]
            total_c = sum(sum(b_dict.values()) for b_dict in counts_dict.values())
            series_items.append(
                MonthlyTransactionSeriesItem(
                    yearMonth=ym,
                    totalCount=total_c,
                    counts=counts_dict
                )
            )

        data = TransactionCountData(
            adminDongCode=admin_dong_code,
            adminDongName=dong_name,
            periodStart=period_start.isoformat(),
            periodEnd=period_end.isoformat(),
            transactionTypes=tx_types,
            buildingTypes=bld_types,
            series=series_items
        )
        return TransactionCountResponse(status=200, message="SUCCESS", data=data)

    @classmethod
    async def get_trades_list(
        cls,
        conn: asyncpg.Connection,
        admin_dong_code: Optional[str],
        period_start: date,
        period_end: date,
        raw_bld_types: Optional[List[str]],
        apt_name: Optional[str],
        min_deal_amount: Optional[int],
        max_deal_amount: Optional[int],
        min_excl_area: Optional[float],
        max_excl_area: Optional[float],
        page: int = 1,
        size: int = 20,
        sort: str = "deal_date,desc"
    ) -> TradeListResponse:
        size = min(max(size, 1), 100)
        page = max(page, 1)
        offset = (page - 1) * size

        sort_col, sort_dir = "deal_date", "DESC"
        if "," in sort:
            parts = sort.split(",")
            sort_col, sort_dir = parts[0].strip(), parts[1].strip()

        bld_types = None
        if raw_bld_types:
            bld_types = []
            for b in raw_bld_types:
                for sub in b.split(","):
                    sub_clean = sub.strip()
                    if sub_clean:
                        bld_types.append(sub_clean)

        total_elements, rows = await TransactionRepository.get_trades_list(
            conn, admin_dong_code, period_start, period_end, bld_types,
            apt_name, min_deal_amount, max_deal_amount, min_excl_area, max_excl_area,
            offset, size, sort_col, sort_dir
        )

        items = []
        for idx, r in enumerate(rows, start=1):
            d_date = r.get("deal_date")
            d_str = d_date.isoformat() if d_date else ""
            d_nodash = d_str.replace("-", "")
            pnu_val = r.get("pnu") or "0000000000000000000"
            rec_id = r.get("id") or idx
            trade_id = f"TR_{d_nodash}_{pnu_val}_{rec_id:02d}"

            items.append(
                TradeItemDTO(
                    tradeId=trade_id,
                    pnu=r.get("pnu"),
                    dealDate=d_str,
                    buildingType=normalize_building_type_code(r.get("house_type")),
                    aptName=r.get("apt_name"),
                    adminDongCode=r.get("admin_dong_code"),
                    adminDongName=r.get("admin_dong_name"),
                    legalDongCode=r.get("legal_dong_code"),
                    legalDongName=r.get("legal_dong_name"),
                    jibunAddress=r.get("jibun_address"),
                    jibun=r.get("jibun"),
                    floor=r.get("floor"),
                    exclArea=float(r.get("excl_area")) if r.get("excl_area") is not None else None,
                    dealAmount=r.get("deal_amount"),
                    pricePerM2=float(r.get("price_per_m2")) if r.get("price_per_m2") is not None else None,
                    buildYear=r.get("build_year"),
                    cancelDealDay=r.get("cancel_deal_day")
                )
            )

        total_pages = math.ceil(total_elements / size) if total_elements > 0 else 0
        pagination = PaginationDTO(
            page=page,
            size=size,
            totalElements=total_elements,
            totalPages=total_pages,
            hasNext=page < total_pages,
            hasPrevious=page > 1
        )

        return TradeListResponse(
            status=200,
            message="SUCCESS",
            data=TradeListData(pagination=pagination, items=items)
        )
