from datetime import date
from typing import Any, Dict, List, Optional, Tuple
import asyncpg


def get_db_house_type_list(building_type: str) -> List[str]:
    v = str(building_type).strip().upper()
    if v in ("APT", "아파트"):
        return ["APT", "아파트"]
    elif v in ("OFFICETEL", "오피스텔"):
        return ["OFFICETEL", "오피스텔"]
    elif v in ("TOWNHOUSE", "연립다세대", "연립·다세대", "연립/다세대", "연립", "다세대", "빌라"):
        return ["TOWNHOUSE", "연립다세대", "연립·다세대", "연립/다세대", "연립", "다세대", "빌라"]
    elif v in ("DETACHED", "단독다가구", "단독/다가구", "단독", "다가구"):
        return ["DETACHED", "단독다가구", "단독/다가구", "단독", "다가구"]
    return [building_type]


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

    @staticmethod
    async def get_monthly_transaction_counts(
        conn: asyncpg.Connection,
        admin_dong_code: str,
        period_start: date,
        period_end: date
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        trade_query = """
            SELECT 
                TO_CHAR(t.deal_date, 'YYYY-MM') AS year_month,
                t.house_type,
                COUNT(*) AS count
            FROM public.transaction_trades t
            LEFT JOIN public.residential_buildings b_exact ON t.pnu = b_exact.pnu
            LEFT JOIN public.residential_buildings b_main ON SUBSTR(t.pnu, 1, 15) || '0000' = SUBSTR(b_main.pnu, 1, 15) || '0000'
            WHERE (t.admin_dong_code = $1 OR COALESCE(b_exact.admin_dong_code, b_main.admin_dong_code) = $1)
              AND t.deal_date >= $2
              AND t.deal_date <= $3
              AND t.cancel_deal_day IS NULL
            GROUP BY TO_CHAR(t.deal_date, 'YYYY-MM'), t.house_type;
        """
        trade_rows = await conn.fetch(trade_query, admin_dong_code, period_start, period_end)

        rent_query = """
            SELECT 
                TO_CHAR(r.deal_date, 'YYYY-MM') AS year_month,
                r.house_type,
                r.rent_type,
                COUNT(*) AS count
            FROM public.transaction_rents r
            LEFT JOIN public.residential_buildings b_exact ON r.pnu = b_exact.pnu
            LEFT JOIN public.residential_buildings b_main ON SUBSTR(r.pnu, 1, 15) || '0000' = SUBSTR(b_main.pnu, 1, 15) || '0000'
            WHERE (r.admin_dong_code = $1 OR COALESCE(b_exact.admin_dong_code, b_main.admin_dong_code) = $1)
              AND r.deal_date >= $2
              AND r.deal_date <= $3
            GROUP BY TO_CHAR(r.deal_date, 'YYYY-MM'), r.house_type, r.rent_type;
        """
        rent_rows = await conn.fetch(rent_query, admin_dong_code, period_start, period_end)

        return [dict(r) for r in trade_rows], [dict(r) for r in rent_rows]

    @staticmethod
    async def get_trades_list(
        conn: asyncpg.Connection,
        admin_dong_code: Optional[str],
        period_start: date,
        period_end: date,
        building_types: Optional[List[str]],
        apt_name: Optional[str],
        min_deal_amount: Optional[int],
        max_deal_amount: Optional[int],
        min_excl_area: Optional[float],
        max_excl_area: Optional[float],
        offset: int,
        limit: int,
        sort_col: str = "deal_date",
        sort_dir: str = "DESC"
    ) -> Tuple[int, List[Dict[str, Any]]]:
        params = [period_start, period_end]
        param_idx = 3

        where_clauses = [
            "t.deal_date >= $1",
            "t.deal_date <= $2"
        ]

        if admin_dong_code:
            where_clauses.append(f"(t.admin_dong_code = ${param_idx} OR COALESCE(b_exact.admin_dong_code, b_main.admin_dong_code) = ${param_idx})")
            params.append(admin_dong_code)
            param_idx += 1

        if building_types:
            expanded_types = []
            for bt in building_types:
                expanded_types.extend(get_db_house_type_list(bt))
            where_clauses.append(f"t.house_type = ANY(${param_idx}::text[])")
            params.append(expanded_types)
            param_idx += 1

        if apt_name:
            where_clauses.append(f"t.apt_name ILIKE ${param_idx}")
            params.append(f"%{apt_name}%")
            param_idx += 1

        if min_deal_amount is not None:
            where_clauses.append(f"t.deal_amount >= ${param_idx}")
            params.append(min_deal_amount)
            param_idx += 1

        if max_deal_amount is not None:
            where_clauses.append(f"t.deal_amount <= ${param_idx}")
            params.append(max_deal_amount)
            param_idx += 1

        if min_excl_area is not None:
            where_clauses.append(f"t.excl_area >= ${param_idx}")
            params.append(min_excl_area)
            param_idx += 1

        if max_excl_area is not None:
            where_clauses.append(f"t.excl_area <= ${param_idx}")
            params.append(max_excl_area)
            param_idx += 1

        where_sql = " AND ".join(where_clauses)

        from_sql = """
            FROM public.transaction_trades t
            LEFT JOIN public.residential_buildings b_exact ON t.pnu = b_exact.pnu
            LEFT JOIN public.residential_buildings b_main ON SUBSTR(t.pnu, 1, 15) || '0000' = SUBSTR(b_main.pnu, 1, 15) || '0000'
        """

        count_query = f"SELECT COUNT(*) {from_sql} WHERE {where_sql};"
        total_count = await conn.fetchval(count_query, *params)

        valid_sort_cols = {
            "deal_date": "t.deal_date",
            "deal_amount": "t.deal_amount",
            "excl_area": "t.excl_area",
            "price_per_m2": "t.price_per_m2",
            "build_year": "t.build_year"
        }
        order_column = valid_sort_cols.get(sort_col.lower(), "t.deal_date")
        order_direction = "DESC" if sort_dir.upper() == "DESC" else "ASC"

        query = f"""
            SELECT 
                t.id,
                t.pnu,
                t.deal_date,
                t.house_type,
                t.apt_name,
                COALESCE(t.admin_dong_code, b_exact.admin_dong_code, b_main.admin_dong_code) AS admin_dong_code,
                COALESCE(t.admin_dong_name, b_exact.admin_dong_name, b_main.admin_dong_name) AS admin_dong_name,
                COALESCE(t.legal_dong_code, b_exact.legal_dong_code, b_main.legal_dong_code) AS legal_dong_code,
                COALESCE(t.legal_dong_name, b_exact.legal_dong_name, b_main.legal_dong_name) AS legal_dong_name,
                COALESCE(t.jibun_address, b_exact.jibun_address, b_main.jibun_address) AS jibun_address,
                COALESCE(t.jibun, b_exact.jibun, b_main.jibun) AS jibun,
                t.floor,
                t.excl_area,
                t.deal_amount,
                t.price_per_m2,
                t.build_year,
                t.cancel_deal_day
            {from_sql}
            WHERE {where_sql}
            ORDER BY {order_column} {order_direction}, t.id DESC
            OFFSET ${param_idx} LIMIT ${param_idx + 1};
        """
        params.extend([offset, limit])
        rows = await conn.fetch(query, *params)

        return total_count, [dict(r) for r in rows]

    @staticmethod
    async def get_rents_list(
        conn: asyncpg.Connection,
        admin_dong_code: Optional[str],
        period_start: date,
        period_end: date,
        rent_type: Optional[str],
        building_types: Optional[List[str]],
        apt_name: Optional[str],
        min_deposit: Optional[int],
        max_deposit: Optional[int],
        min_monthly_rent: Optional[int],
        max_monthly_rent: Optional[int],
        min_excl_area: Optional[float],
        max_excl_area: Optional[float],
        offset: int,
        limit: int,
        sort_col: str = "deal_date",
        sort_dir: str = "DESC"
    ) -> Tuple[int, List[Dict[str, Any]]]:
        params = [period_start, period_end]
        param_idx = 3

        where_clauses = [
            "r.deal_date >= $1",
            "r.deal_date <= $2"
        ]

        if admin_dong_code:
            where_clauses.append(f"(r.admin_dong_code = ${param_idx} OR COALESCE(b_exact.admin_dong_code, b_main.admin_dong_code) = ${param_idx})")
            params.append(admin_dong_code)
            param_idx += 1

        if rent_type and rent_type.upper() in ("JEONSE", "MONTHLY", "전세", "월세"):
            r_str = "전세" if rent_type.upper() in ("JEONSE", "전세") else "월세"
            where_clauses.append(f"r.rent_type = ${param_idx}")
            params.append(r_str)
            param_idx += 1

        if building_types:
            expanded_types = []
            for bt in building_types:
                expanded_types.extend(get_db_house_type_list(bt))
            where_clauses.append(f"r.house_type = ANY(${param_idx}::text[])")
            params.append(expanded_types)
            param_idx += 1

        if apt_name:
            where_clauses.append(f"r.apt_name ILIKE ${param_idx}")
            params.append(f"%{apt_name}%")
            param_idx += 1

        if min_deposit is not None:
            where_clauses.append(f"r.deposit >= ${param_idx}")
            params.append(min_deposit)
            param_idx += 1

        if max_deposit is not None:
            where_clauses.append(f"r.deposit <= ${param_idx}")
            params.append(max_deposit)
            param_idx += 1

        if min_monthly_rent is not None:
            where_clauses.append(f"r.monthly_rent >= ${param_idx}")
            params.append(min_monthly_rent)
            param_idx += 1

        if max_monthly_rent is not None:
            where_clauses.append(f"r.monthly_rent <= ${param_idx}")
            params.append(max_monthly_rent)
            param_idx += 1

        if min_excl_area is not None:
            where_clauses.append(f"r.excl_area >= ${param_idx}")
            params.append(min_excl_area)
            param_idx += 1

        if max_excl_area is not None:
            where_clauses.append(f"r.excl_area <= ${param_idx}")
            params.append(max_excl_area)
            param_idx += 1

        where_sql = " AND ".join(where_clauses)

        from_sql = """
            FROM public.transaction_rents r
            LEFT JOIN public.residential_buildings b_exact ON r.pnu = b_exact.pnu
            LEFT JOIN public.residential_buildings b_main ON SUBSTR(r.pnu, 1, 15) || '0000' = SUBSTR(b_main.pnu, 1, 15) || '0000'
        """

        count_query = f"SELECT COUNT(*) {from_sql} WHERE {where_sql};"
        total_count = await conn.fetchval(count_query, *params)

        valid_sort_cols = {
            "deal_date": "r.deal_date",
            "deposit": "r.deposit",
            "monthly_rent": "r.monthly_rent",
            "excl_area": "r.excl_area"
        }
        order_column = valid_sort_cols.get(sort_col.lower(), "r.deal_date")
        order_direction = "DESC" if sort_dir.upper() == "DESC" else "ASC"

        query = f"""
            SELECT 
                r.id,
                r.pnu,
                r.deal_date,
                r.rent_type,
                r.house_type,
                r.apt_name,
                COALESCE(r.admin_dong_code, b_exact.admin_dong_code, b_main.admin_dong_code) AS admin_dong_code,
                COALESCE(r.admin_dong_name, b_exact.admin_dong_name, b_main.admin_dong_name) AS admin_dong_name,
                COALESCE(r.legal_dong_code, b_exact.legal_dong_code, b_main.legal_dong_code) AS legal_dong_code,
                COALESCE(r.legal_dong_name, b_exact.legal_dong_name, b_main.legal_dong_name) AS legal_dong_name,
                COALESCE(r.jibun_address, b_exact.jibun_address, b_main.jibun_address) AS jibun_address,
                COALESCE(r.jibun, b_exact.jibun, b_main.jibun) AS jibun,
                r.floor,
                r.excl_area,
                r.deposit,
                r.monthly_rent,
                r.contract_period,
                r.use_rr_right
            {from_sql}
            WHERE {where_sql}
            ORDER BY {order_column} {order_direction}, r.id DESC
            OFFSET ${param_idx} LIMIT ${param_idx + 1};
        """
        params.extend([offset, limit])
        rows = await conn.fetch(query, *params)

        return total_count, [dict(r) for r in rows]
