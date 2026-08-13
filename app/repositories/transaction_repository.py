from typing import Any, Dict, List, Optional
import asyncpg


def normalize_building_type_code(house_type_str: Optional[str]) -> str:
    if not house_type_str:
        return "APT"
    v = str(house_type_str).strip().upper()
    if any(k in v for k in ["APT", "아파트"]):
        return "APT"
    elif any(k in v for k in ["OFFICETEL", "오피스텔"]):
        return "OFFICETEL"
    elif any(k in v for k in ["TOWNHOUSE", "연립", "다세대", "빌라"]):
        return "TOWNHOUSE"
    elif any(k in v for k in ["DETACHED", "단독", "다가구"]):
        return "DETACHED"
    return "APT"


class TransactionRepository:

    @staticmethod
    async def get_admin_dong_info(conn: asyncpg.Connection, admin_dong_code: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT admin_dong_code, admin_dong_name, legal_dong_name
            FROM public.admin_dong
            WHERE admin_dong_code = $1
            LIMIT 1;
        """
        row = await conn.fetchrow(query, admin_dong_code)
        if not row:
            return None
        return dict(row)

    @staticmethod
    async def get_housing_stock_counts(conn: asyncpg.Connection, admin_dong_code: str) -> List[Dict[str, Any]]:
        query = """
            SELECT house_type, COUNT(*) AS count
            FROM public.transaction_trades
            WHERE admin_dong_code = $1
              AND cancel_deal_day IS NULL
            GROUP BY house_type;
        """
        rows = await conn.fetch(query, admin_dong_code)
        if rows:
            return [dict(r) for r in rows]

        fallback_query = """
            SELECT property_category AS house_type, COUNT(*) AS count
            FROM public.residential_buildings
            WHERE admin_dong_code = $1
            GROUP BY property_category;
        """
        fb_rows = await conn.fetch(fallback_query, admin_dong_code)
        return [dict(r) for r in fb_rows]
