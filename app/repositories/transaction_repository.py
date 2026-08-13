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

    @staticmethod
    async def get_developments_list(
        conn: asyncpg.Connection,
        admin_dong_code: Optional[str],
        dev_type: Optional[str],
        project_name: Optional[str],
        stage_code: Optional[str],
        is_completed: Optional[bool],
        pnu: Optional[str],
        offset: int,
        limit: int
    ) -> Tuple[int, List[Dict[str, Any]]]:
        params = []
        param_idx = 1
        where_clauses = []

        if admin_dong_code:
            where_clauses.append(f"admin_dong_code = ${param_idx}")
            params.append(admin_dong_code)
            param_idx += 1

        if dev_type and dev_type.upper() in ("REDEVELOPMENT", "RECONSTRUCTION", "재개발", "재건축"):
            dt_str = "재개발" if dev_type.upper() in ("REDEVELOPMENT", "재개발") else "재건축"
            where_clauses.append(f"dev_type = ${param_idx}")
            params.append(dt_str)
            param_idx += 1

        if project_name:
            where_clauses.append(f"project_name ILIKE ${param_idx}")
            params.append(f"%{project_name}%")
            param_idx += 1

        if stage_code:
            where_clauses.append(f"stage_code = ${param_idx}")
            params.append(stage_code)
            param_idx += 1

        if is_completed is not None:
            where_clauses.append(f"is_completed = ${param_idx}")
            params.append(is_completed)
            param_idx += 1

        if pnu:
            where_clauses.append(f"pnu = ${param_idx}")
            params.append(pnu)
            param_idx += 1

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        count_query = f"SELECT COUNT(DISTINCT COALESCE(pnu, project_name)) FROM public.history_developments {where_sql};"
        total_projects = await conn.fetchval(count_query, *params)

        project_keys_query = f"""
            SELECT COALESCE(pnu, project_name) AS proj_key, MAX(id) as max_id
            FROM public.history_developments
            {where_sql}
            GROUP BY COALESCE(pnu, project_name)
            ORDER BY max_id DESC
            OFFSET ${param_idx} LIMIT ${param_idx + 1};
        """
        params.extend([offset, limit])
        proj_rows = await conn.fetch(project_keys_query, *params)
        proj_keys = [r['proj_key'] for r in proj_rows]

        if not proj_keys:
            return total_projects, []

        records_query = """
            SELECT * FROM public.history_developments
            WHERE COALESCE(pnu, project_name) = ANY($1::text[])
            ORDER BY id ASC;
        """
        all_records = await conn.fetch(records_query, proj_keys)
        return total_projects, [dict(r) for r in all_records]

    @staticmethod
    async def get_development_detail(
        conn: asyncpg.Connection,
        project_id: str
    ) -> List[Dict[str, Any]]:
        target_key = project_id[4:] if project_id.startswith("DEV_") else project_id
        query = """
            SELECT * FROM public.history_developments
            WHERE pnu = $1 
               OR project_name = $1 
               OR pnu = $2 
               OR project_name = $2
               OR completed_apt_name = $1
               OR completed_apt_name = $2
            ORDER BY id ASC;
        """
        rows = await conn.fetch(query, project_id, target_key)
        return [dict(r) for r in rows]


    @staticmethod
    async def get_buildings_list(
        conn: asyncpg.Connection,
        admin_dong_code: Optional[str],
        building_types: Optional[List[str]],
        building_name: Optional[str],
        offset: int,
        limit: int
    ) -> Tuple[int, List[Dict[str, Any]]]:
        params = []
        param_idx = 1
        where_clauses = []

        if admin_dong_code:
            where_clauses.append(f"(b.admin_dong_code = ${param_idx} OR ad.admin_dong_code = ${param_idx})")
            params.append(admin_dong_code)
            param_idx += 1

        if building_types:
            expanded_types = []
            for bt in building_types:
                expanded_types.extend(get_db_house_type_list(bt))
            where_clauses.append(f"b.property_category = ANY(${param_idx}::text[])")
            params.append(expanded_types)
            param_idx += 1

        if building_name:
            where_clauses.append(f"COALESCE(b.property_name, b.jibun_address) ILIKE ${param_idx}")
            params.append(f"%{building_name}%")
            param_idx += 1

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        from_sql = """
            FROM public.residential_buildings b
            LEFT JOIN public.admin_dong ad ON b.legal_dong_name = ad.legal_dong_name OR b.admin_dong_code = ad.admin_dong_code
        """

        count_query = f"SELECT COUNT(DISTINCT b.pnu) {from_sql} {where_sql};"
        total_count = await conn.fetchval(count_query, *params)

        query = f"""
            SELECT DISTINCT ON (b.pnu)
                b.pnu,
                COALESCE(b.property_name, b.jibun_address) AS building_name,
                b.property_category AS building_type,
                COALESCE(b.admin_dong_code, ad.admin_dong_code) AS admin_dong_code,
                COALESCE(b.admin_dong_name, ad.admin_dong_name) AS admin_dong_name,
                b.legal_dong_code,
                b.legal_dong_name,
                b.jibun_address,
                b.jibun,
                b.total_households,
                b.total_parking,
                b.use_approval_date
            {from_sql}
            {where_sql}
            ORDER BY b.pnu ASC
            OFFSET ${param_idx} LIMIT ${param_idx + 1};
        """
        params.extend([offset, limit])
        rows = await conn.fetch(query, *params)

        return total_count, [dict(r) for r in rows]

    @staticmethod
    async def get_building_unit_types(
        conn: asyncpg.Connection,
        pnu: Optional[str],
        building_name: Optional[str],
        admin_dong_code: Optional[str]
    ) -> List[Dict[str, Any]]:
        params = []
        param_idx = 1
        where_clauses = []

        if pnu:
            where_clauses.append(f"b.pnu = ${param_idx}")
            params.append(pnu)
            param_idx += 1

        if building_name:
            where_clauses.append(f"COALESCE(b.property_name, b.jibun_address) ILIKE ${param_idx}")
            params.append(f"%{building_name}%")
            param_idx += 1

        if admin_dong_code:
            where_clauses.append(f"(b.admin_dong_code = ${param_idx} OR ad.admin_dong_code = ${param_idx})")
            params.append(admin_dong_code)
            param_idx += 1

        if not where_clauses:
            return []

        where_sql = "WHERE " + " AND ".join(where_clauses)

        query = f"""
            SELECT 
                b.pnu,
                COALESCE(b.property_name, b.jibun_address) AS building_name,
                b.property_category AS building_type,
                COALESCE(b.admin_dong_code, ad.admin_dong_code) AS admin_dong_code,
                COALESCE(b.admin_dong_name, ad.admin_dong_name) AS admin_dong_name,
                b.legal_dong_code,
                b.legal_dong_name,
                b.jibun_address,
                b.total_households,
                b.total_parking,
                b.use_approval_date,
                u.id AS unit_id,
                u.exclusive_area,
                u.pyung_type,
                u.household_count
            FROM public.residential_buildings b
            JOIN public.residential_buildings_unit_types u ON b.pnu = u.pnu
            LEFT JOIN public.admin_dong ad ON b.legal_dong_name = ad.legal_dong_name OR b.admin_dong_code = ad.admin_dong_code
            {where_sql}
            ORDER BY b.pnu ASC, u.pyung_type ASC, u.exclusive_area ASC;
        """
        rows = await conn.fetch(query, *params)
        return [dict(r) for r in rows]

    @staticmethod
    async def get_building_detail_summary(
        conn: asyncpg.Connection,
        pnu: str
    ) -> Optional[Dict[str, Any]]:
        # 1. Fetch building master info
        info_query = """
            SELECT 
                b.pnu,
                COALESCE(b.property_name, b.jibun_address) AS building_name,
                b.property_category AS building_type,
                COALESCE(b.admin_dong_code, ad.admin_dong_code) AS admin_dong_code,
                COALESCE(b.admin_dong_name, ad.admin_dong_name) AS admin_dong_name,
                b.legal_dong_code,
                b.legal_dong_name,
                b.jibun_address,
                b.jibun,
                b.total_households,
                b.total_parking,
                b.use_approval_date::text AS use_approval_date
            FROM public.residential_buildings b
            LEFT JOIN public.admin_dong ad ON b.legal_dong_name = ad.legal_dong_name OR b.admin_dong_code = ad.admin_dong_code
            WHERE b.pnu = $1
            LIMIT 1;
        """
        info_row = await conn.fetchrow(info_query, pnu)
        
        building_info = dict(info_row) if info_row else None

        # Fallback if not found in residential_buildings master table: check transaction_trades
        if not building_info:
            fb_query = """
                SELECT 
                    t.pnu,
                    t.apt_name AS building_name,
                    t.house_type AS building_type,
                    t.admin_dong_code,
                    t.admin_dong_name,
                    t.legal_dong_code,
                    t.legal_dong_name,
                    t.jibun_address,
                    t.jibun,
                    NULL::int AS total_households,
                    NULL::int AS total_parking,
                    t.build_year::text AS use_approval_date
                FROM public.transaction_trades t
                WHERE t.pnu = $1 OR SUBSTR(t.pnu, 1, 15) || '0000' = SUBSTR($1, 1, 15) || '0000'
                LIMIT 1;
            """
            fb_row = await conn.fetchrow(fb_query, pnu)
            if not fb_row:
                return None
            building_info = dict(fb_row)

        # 2. Fetch unit types
        units_query = """
            SELECT 
                exclusive_area,
                pyung_type,
                household_count
            FROM public.residential_buildings_unit_types
            WHERE pnu = $1
            ORDER BY pyung_type ASC, exclusive_area ASC;
        """
        units_rows = await conn.fetch(units_query, pnu)
        unit_types = [dict(r) for r in units_rows]

        # 3. Fetch all trades for this PNU for unit-level aggregation and recent trades
        trades_query = """
            SELECT 
                t.id::text,
                'TRADE' AS trade_type,
                t.deal_date::text,
                t.floor,
                t.excl_area,
                t.deal_amount,
                NULL::int AS monthly_rent,
                t.price_per_m2
            FROM public.transaction_trades t
            WHERE (t.pnu = $1 OR SUBSTR(t.pnu, 1, 15) || '0000' = SUBSTR($1, 1, 15) || '0000')
              AND t.cancel_deal_day IS NULL
            ORDER BY t.deal_date DESC;
        """
        trades_rows = await conn.fetch(trades_query, pnu)
        trades_list = [dict(r) for r in trades_rows]

        # 4. Fetch all rents for this PNU
        rents_query = """
            SELECT 
                r.id::text,
                r.rent_type AS trade_type,
                r.deal_date::text,
                r.floor,
                r.excl_area,
                r.deposit AS deal_amount,
                r.monthly_rent,
                NULL::float AS price_per_m2
            FROM public.transaction_rents r
            WHERE (r.pnu = $1 OR SUBSTR(r.pnu, 1, 15) || '0000' = SUBSTR($1, 1, 15) || '0000')
            ORDER BY r.deal_date DESC;
        """
        rents_rows = await conn.fetch(rents_query, pnu)
        rents_list = [dict(r) for r in rents_rows]

        # 5. Fetch monthly price trends
        trends_query = """
            WITH trades_agg AS (
                SELECT 
                    TO_CHAR(t.deal_date, 'YYYY-MM') AS ym,
                    ROUND(AVG(t.deal_amount)) AS avg_trade,
                    COUNT(*) AS trade_cnt
                FROM public.transaction_trades t
                WHERE (t.pnu = $1 OR SUBSTR(t.pnu, 1, 15) || '0000' = SUBSTR($1, 1, 15) || '0000')
                  AND t.cancel_deal_day IS NULL
                GROUP BY TO_CHAR(t.deal_date, 'YYYY-MM')
            ),
            rents_agg AS (
                SELECT 
                    TO_CHAR(r.deal_date, 'YYYY-MM') AS ym,
                    ROUND(AVG(r.deposit)) AS avg_rent,
                    COUNT(*) AS rent_cnt
                FROM public.transaction_rents r
                WHERE (r.pnu = $1 OR SUBSTR(r.pnu, 1, 15) || '0000' = SUBSTR($1, 1, 15) || '0000')
                GROUP BY TO_CHAR(r.deal_date, 'YYYY-MM')
            )
            SELECT 
                COALESCE(t.ym, r.ym) AS year_month,
                t.avg_trade::int AS avg_trade_amount,
                COALESCE(t.trade_cnt, 0)::int AS trade_count,
                r.avg_rent::int AS avg_rent_deposit,
                COALESCE(r.rent_cnt, 0)::int AS rent_count
            FROM trades_agg t
            FULL OUTER JOIN rents_agg r ON t.ym = r.ym
            ORDER BY year_month ASC;
        """
        trends_rows = await conn.fetch(trends_query, pnu)
        price_trends = [dict(r) for r in trends_rows]

        return {
            "building_info": building_info,
            "unit_types": unit_types,
            "trades": trades_list,
            "rents": rents_list,
            "price_trends": price_trends,
        }

    @staticmethod
    async def get_dong_trends_summary(
        conn: asyncpg.Connection,
        admin_dong_code: str,
        period_months: int = 3,
        building_types: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        # 1. Fetch base admin_dong info & adjacent dong codes
        dong_query = """
            SELECT admin_dong_code, admin_dong_name, legal_dong_name, adjacent_dong_codes, adjacent_dong_names
            FROM public.admin_dong
            WHERE admin_dong_code = $1
            LIMIT 1;
        """
        dong_row = await conn.fetchrow(dong_query, admin_dong_code)
        if not dong_row:
            return None

        base_info = dict(dong_row)
        adj_codes_raw = base_info.get("adjacent_dong_codes") or ""
        adj_codes = [c.strip() for c in adj_codes_raw.split(",") if c.strip()]

        # Fetch adjacent dongs info (codes & names)
        adj_info_rows = []
        if adj_codes:
            adj_query = """
                SELECT admin_dong_code, admin_dong_name
                FROM public.admin_dong
                WHERE admin_dong_code = ANY($1::text[]);
            """
            adj_info_rows = [dict(r) for r in await conn.fetch(adj_query, adj_codes)]

        # 2. Determine max deal_date in dataset to calculate current and previous period date bounds
        max_date_query = "SELECT MAX(deal_date) FROM public.transaction_trades;"
        max_date = await conn.fetchval(max_date_query) or date.today()

        from dateutil.relativedelta import relativedelta
        curr_start = max_date - relativedelta(months=period_months)
        prev_start = curr_start - relativedelta(months=period_months)

        gu_code_prefix = admin_dong_code[:5]

        # 3. Base dong trades & rents
        b_trades_curr_q = """
            SELECT t.deal_amount, t.excl_area, t.price_per_m2, t.deal_date
            FROM public.transaction_trades t
            LEFT JOIN public.residential_buildings b ON t.pnu = b.pnu
            WHERE (t.admin_dong_code = $3 OR b.admin_dong_code = $3)
              AND t.deal_date >= $1 AND t.deal_date <= $2 AND t.cancel_deal_day IS NULL;
        """
        b_trades_curr = [dict(r) for r in await conn.fetch(b_trades_curr_q, curr_start, max_date, admin_dong_code)]

        b_trades_prev_q = """
            SELECT t.deal_amount, t.excl_area, t.price_per_m2, t.deal_date
            FROM public.transaction_trades t
            LEFT JOIN public.residential_buildings b ON t.pnu = b.pnu
            WHERE (t.admin_dong_code = $3 OR b.admin_dong_code = $3)
              AND t.deal_date >= $1 AND t.deal_date < $2 AND t.cancel_deal_day IS NULL;
        """
        b_trades_prev = [dict(r) for r in await conn.fetch(b_trades_prev_q, prev_start, curr_start, admin_dong_code)]

        b_rents_curr_q = """
            SELECT r.deposit, r.monthly_rent, r.excl_area, r.rent_type, r.deal_date
            FROM public.transaction_rents r
            LEFT JOIN public.residential_buildings b ON r.pnu = b.pnu
            WHERE (r.admin_dong_code = $3 OR b.admin_dong_code = $3)
              AND r.deal_date >= $1 AND r.deal_date <= $2;
        """
        b_rents_curr = [dict(r) for r in await conn.fetch(b_rents_curr_q, curr_start, max_date, admin_dong_code)]

        b_rents_prev_q = """
            SELECT r.deposit, r.monthly_rent, r.excl_area, r.rent_type, r.deal_date
            FROM public.transaction_rents r
            LEFT JOIN public.residential_buildings b ON r.pnu = b.pnu
            WHERE (r.admin_dong_code = $3 OR b.admin_dong_code = $3)
              AND r.deal_date >= $1 AND r.deal_date < $2;
        """
        b_rents_prev = [dict(r) for r in await conn.fetch(b_rents_prev_q, prev_start, curr_start, admin_dong_code)]

        # 4. Adjacent dongs trades & rents
        adj_trades_map = {}
        adj_rents_map = {}
        if adj_codes:
            adj_trades_curr_q = """
                SELECT COALESCE(t.admin_dong_code, b.admin_dong_code) AS dong_code, t.deal_amount, t.excl_area, t.price_per_m2
                FROM public.transaction_trades t
                LEFT JOIN public.residential_buildings b ON t.pnu = b.pnu
                WHERE COALESCE(t.admin_dong_code, b.admin_dong_code) = ANY($3::text[])
                  AND t.deal_date >= $1 AND t.deal_date <= $2 AND t.cancel_deal_day IS NULL;
            """
            for r in await conn.fetch(adj_trades_curr_q, curr_start, max_date, adj_codes):
                code = r["dong_code"]
                if code not in adj_trades_map:
                    adj_trades_map[code] = []
                adj_trades_map[code].append(dict(r))

            adj_rents_curr_q = """
                SELECT COALESCE(r.admin_dong_code, b.admin_dong_code) AS dong_code, r.deposit, r.excl_area, r.rent_type
                FROM public.transaction_rents r
                LEFT JOIN public.residential_buildings b ON r.pnu = b.pnu
                WHERE COALESCE(r.admin_dong_code, b.admin_dong_code) = ANY($3::text[])
                  AND r.deal_date >= $1 AND r.deal_date <= $2;
            """
            for r in await conn.fetch(adj_rents_curr_q, curr_start, max_date, adj_codes):
                code = r["dong_code"]
                if code not in adj_rents_map:
                    adj_rents_map[code] = []
                adj_rents_map[code].append(dict(r))

        # 5. Gu level trades
        gu_trades_curr_q = """
            SELECT t.deal_amount, t.excl_area, t.price_per_m2
            FROM public.transaction_trades t
            WHERE SUBSTR(t.admin_dong_code, 1, 5) = $3
              AND t.deal_date >= $1 AND t.deal_date <= $2 AND t.cancel_deal_day IS NULL;
        """
        gu_trades_curr = [dict(r) for r in await conn.fetch(gu_trades_curr_q, curr_start, max_date, gu_code_prefix)]

        gu_trades_prev_q = """
            SELECT t.deal_amount, t.excl_area, t.price_per_m2
            FROM public.transaction_trades t
            WHERE SUBSTR(t.admin_dong_code, 1, 5) = $3
              AND t.deal_date >= $1 AND t.deal_date < $2 AND t.cancel_deal_day IS NULL;
        """
        gu_trades_prev = [dict(r) for r in await conn.fetch(gu_trades_prev_q, prev_start, curr_start, gu_code_prefix)]

        return {
            "base_info": base_info,
            "adj_info_rows": adj_info_rows,
            "base_trades_curr": b_trades_curr,
            "base_trades_prev": b_trades_prev,
            "base_rents_curr": b_rents_curr,
            "base_rents_prev": b_rents_prev,
            "adj_trades_map": adj_trades_map,
            "adj_rents_map": adj_rents_map,
            "gu_trades_curr": gu_trades_curr,
            "gu_trades_prev": gu_trades_prev,
            "period_months": period_months,
        }

    @staticmethod
    async def get_region_stat(
        conn: asyncpg.Connection,
        admin_dong_code: str,
        period_months: int = 3
    ) -> Optional[Dict[str, Any]]:
        dong_query = """
            SELECT admin_dong_code, admin_dong_name, legal_dong_name
            FROM public.admin_dong
            WHERE admin_dong_code = $1
            LIMIT 1;
        """
        dong_row = await conn.fetchrow(dong_query, admin_dong_code)
        if not dong_row:
            return None

        dong_info = dict(dong_row)

        max_date_query = "SELECT MAX(deal_date) FROM public.transaction_trades;"
        max_date = await conn.fetchval(max_date_query) or date.today()

        from dateutil.relativedelta import relativedelta
        curr_start = max_date - relativedelta(months=period_months)
        prev_start = curr_start - relativedelta(months=period_months)

        trades_curr_q = """
            SELECT t.deal_amount, t.excl_area, t.price_per_m2
            FROM public.transaction_trades t
            LEFT JOIN public.residential_buildings b ON t.pnu = b.pnu
            WHERE (t.admin_dong_code = $3 OR b.admin_dong_code = $3)
              AND t.deal_date >= $1 AND t.deal_date <= $2 AND t.cancel_deal_day IS NULL;
        """
        trades_curr = [dict(r) for r in await conn.fetch(trades_curr_q, curr_start, max_date, admin_dong_code)]

        trades_prev_q = """
            SELECT t.deal_amount, t.excl_area, t.price_per_m2
            FROM public.transaction_trades t
            LEFT JOIN public.residential_buildings b ON t.pnu = b.pnu
            WHERE (t.admin_dong_code = $3 OR b.admin_dong_code = $3)
              AND t.deal_date >= $1 AND t.deal_date < $2 AND t.cancel_deal_day IS NULL;
        """
        trades_prev = [dict(r) for r in await conn.fetch(trades_prev_q, prev_start, curr_start, admin_dong_code)]

        rents_curr_q = """
            SELECT r.deposit, r.monthly_rent, r.excl_area, r.rent_type
            FROM public.transaction_rents r
            LEFT JOIN public.residential_buildings b ON r.pnu = b.pnu
            WHERE (r.admin_dong_code = $3 OR b.admin_dong_code = $3)
              AND r.deal_date >= $1 AND r.deal_date <= $2;
        """
        rents_curr = [dict(r) for r in await conn.fetch(rents_curr_q, curr_start, max_date, admin_dong_code)]

        rents_prev_q = """
            SELECT r.deposit, r.monthly_rent, r.excl_area, r.rent_type
            FROM public.transaction_rents r
            LEFT JOIN public.residential_buildings b ON r.pnu = b.pnu
            WHERE (r.admin_dong_code = $3 OR b.admin_dong_code = $3)
              AND r.deal_date >= $1 AND r.deal_date < $2;
        """
        rents_prev = [dict(r) for r in await conn.fetch(rents_prev_q, prev_start, curr_start, admin_dong_code)]

        return {
            "dong_info": dong_info,
            "trades_curr": trades_curr,
            "trades_prev": trades_prev,
            "rents_curr": rents_curr,
            "rents_prev": rents_prev
        }




