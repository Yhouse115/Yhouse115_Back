from datetime import date
import math
from typing import Dict, List, Optional
import asyncpg
from fastapi import HTTPException, status

from app.repositories.transaction_repository import (
    TransactionRepository,
    normalize_building_type_code,
)
from app.schemas.transaction import (
    BuildingItemDTO,
    BuildingListData,
    BuildingListResponse,
    BuildingUnitsData,
    BuildingUnitsResponse,
    BuildingWithUnitsDTO,
    DevStageItemDTO,
    DevelopmentItemDTO,
    DevelopmentListData,
    DevelopmentListResponse,
    InventoryItemDTO,
    InventorySummaryResponse,
    MonthlyTransactionSeriesItem,
    PaginationDTO,
    RentItemDTO,
    RentListData,
    RentListResponse,
    TradeItemDTO,
    TradeListData,
    TradeListResponse,
    TransactionCountData,
    TransactionCountResponse,
    UnitTypeItemDTO,
)


def parse_comma_or_json_list(val: Optional[str]) -> List[str]:
    if not val:
        return []
    val_str = str(val).strip()
    if val_str.startswith("[") and val_str.endswith("]"):
        import json
        try:
            parsed = json.loads(val_str)
            return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            pass
    return [x.strip() for x in val_str.split(",") if x.strip()]


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

    @classmethod
    async def get_rents_list(
        cls,
        conn: asyncpg.Connection,
        admin_dong_code: Optional[str],
        period_start: date,
        period_end: date,
        rent_type: Optional[str],
        raw_bld_types: Optional[List[str]],
        apt_name: Optional[str],
        min_deposit: Optional[int],
        max_deposit: Optional[int],
        min_monthly_rent: Optional[int],
        max_monthly_rent: Optional[int],
        min_excl_area: Optional[float],
        max_excl_area: Optional[float],
        page: int = 1,
        size: int = 20,
        sort: str = "deal_date,desc"
    ) -> RentListResponse:
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

        total_elements, rows = await TransactionRepository.get_rents_list(
            conn, admin_dong_code, period_start, period_end, rent_type, bld_types,
            apt_name, min_deposit, max_deposit, min_monthly_rent, max_monthly_rent,
            min_excl_area, max_excl_area, offset, size, sort_col, sort_dir
        )

        items = []
        for idx, r in enumerate(rows, start=1):
            d_date = r.get("deal_date")
            d_str = d_date.isoformat() if d_date else ""
            d_nodash = d_str.replace("-", "")
            pnu_val = r.get("pnu") or "0000000000000000000"
            rec_id = r.get("id") or idx
            rent_id = f"RN_{d_nodash}_{pnu_val}_{rec_id:02d}"

            r_type_raw = str(r.get("rent_type") or "").strip()
            r_type_code = "JEONSE" if r_type_raw == "전세" else ("MONTHLY" if r_type_raw == "월세" else r_type_raw)

            items.append(
                RentItemDTO(
                    rentId=rent_id,
                    pnu=r.get("pnu"),
                    dealDate=d_str,
                    rentType=r_type_code,
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
                    deposit=r.get("deposit"),
                    monthlyRent=r.get("monthly_rent"),
                    contractPeriod=r.get("contract_period"),
                    useRrRight=r.get("use_rr_right")
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

        return RentListResponse(
            status=200,
            message="SUCCESS",
            data=RentListData(pagination=pagination, items=items)
        )

    @classmethod
    async def get_developments_list(
        cls,
        conn: asyncpg.Connection,
        admin_dong_code: Optional[str],
        dev_type: Optional[str],
        project_name: Optional[str],
        stage_code: Optional[str],
        is_completed: Optional[bool],
        pnu: Optional[str],
        page: int = 1,
        size: int = 20
    ) -> DevelopmentListResponse:
        size = min(max(size, 1), 100)
        page = max(page, 1)
        offset = (page - 1) * size

        total_elements, rows = await TransactionRepository.get_developments_list(
            conn, admin_dong_code, dev_type, project_name, stage_code, is_completed, pnu, offset, size
        )

        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for r in rows:
            pkey = r.get("pnu") or r.get("project_name")
            if pkey not in grouped:
                grouped[pkey] = []
            grouped[pkey].append(r)

        items = []
        for pkey, p_rows in grouped.items():
            base_r = p_rows[0]
            rep_pnu = base_r.get("pnu") or ""
            proj_id = f"DEV_{rep_pnu}" if rep_pnu else f"DEV_{abs(hash(pkey))}"

            curr_stage_dto = None
            history_dtos = []

            for r in p_rows:
                st_code = r.get("stage_code") or "STAGE_1"
                st_name = r.get("stage_name") or ""
                ev_date = r.get("event_date").isoformat() if r.get("event_date") else None
                st_detail = r.get("status_detail") or ""
                is_curr = r.get("is_current_stage", False)
                is_comp = r.get("is_completed", False)

                stage_dto = DevStageItemDTO(
                    stageCode=st_code,
                    stageName=st_name,
                    eventDate=ev_date,
                    isCurrentStage=is_curr,
                    isCompleted=is_comp,
                    statusDetail=st_detail
                )
                history_dtos.append(stage_dto)

                if is_curr:
                    curr_stage_dto = stage_dto

            if not curr_stage_dto and history_dtos:
                curr_stage_dto = history_dtos[-1]

            items.append(
                DevelopmentItemDTO(
                    projectId=proj_id,
                    pnu=base_r.get("pnu"),
                    projectName=base_r.get("project_name") or "",
                    completedAptName=base_r.get("completed_apt_name"),
                    devType=base_r.get("dev_type"),
                    targetHouseholds=base_r.get("target_households"),
                    adminDongCode=base_r.get("admin_dong_code"),
                    adminDongName=base_r.get("admin_dong_name"),
                    legalDongCode=base_r.get("legal_dong_code"),
                    legalDongName=base_r.get("legal_dong_name"),
                    address=base_r.get("address"),
                    jibunAddress=base_r.get("jibun_address"),
                    includedJibuns=parse_comma_or_json_list(base_r.get("included_jibuns")),
                    includedPnus=parse_comma_or_json_list(base_r.get("included_pnus")),
                    includedApts=parse_comma_or_json_list(base_r.get("included_apts")),
                    currentStage=curr_stage_dto,
                    history=history_dtos
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

        return DevelopmentListResponse(
            status=200,
            message="SUCCESS",
            data=DevelopmentListData(pagination=pagination, items=items)
        )

    @classmethod
    async def get_buildings_list(
        cls,
        conn: asyncpg.Connection,
        admin_dong_code: Optional[str],
        raw_bld_types: Optional[List[str]],
        building_name: Optional[str],
        page: int = 1,
        size: int = 20
    ) -> BuildingListResponse:
        size = min(max(size, 1), 100)
        page = max(page, 1)
        offset = (page - 1) * size

        bld_types = None
        if raw_bld_types:
            bld_types = []
            for b in raw_bld_types:
                for sub in b.split(","):
                    sub_clean = sub.strip()
                    if sub_clean:
                        bld_types.append(sub_clean)

        total_elements, rows = await TransactionRepository.get_buildings_list(
            conn, admin_dong_code, bld_types, building_name, offset, size
        )

        items = []
        for r in rows:
            u_date = r.get("use_approval_date")
            u_str = u_date.isoformat() if u_date else None
            b_year = u_date.year if u_date else None

            items.append(
                BuildingItemDTO(
                    pnu=r.get("pnu") or "",
                    buildingName=r.get("building_name"),
                    buildingType=normalize_building_type_code(r.get("building_type")),
                    adminDongCode=r.get("admin_dong_code"),
                    adminDongName=r.get("admin_dong_name"),
                    legalDongCode=r.get("legal_dong_code"),
                    legalDongName=r.get("legal_dong_name"),
                    jibunAddress=r.get("jibun_address"),
                    jibun=r.get("jibun"),
                    totalHouseholds=r.get("total_households"),
                    totalParking=r.get("total_parking"),
                    useApprovalDate=u_str,
                    buildYear=b_year
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

        return BuildingListResponse(
            status=200,
            message="SUCCESS",
            data=BuildingListData(pagination=pagination, items=items)
        )

    @classmethod
    async def get_building_unit_types(
        cls,
        conn: asyncpg.Connection,
        pnu: Optional[str],
        building_name: Optional[str],
        admin_dong_code: Optional[str]
    ) -> BuildingUnitsResponse:
        if not pnu and not building_name and not admin_dong_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one search parameter (pnu, building_name, admin_dong_code) is required."
            )

        rows = await TransactionRepository.get_building_unit_types(
            conn, pnu, building_name, admin_dong_code
        )

        if not rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="UNIT_TYPES_NOT_FOUND: 평형 정보를 제공할 수 없거나 해당 건축물의 평형 상세 정보가 존재하지 않습니다."
            )

        grouped: Dict[str, Dict[str, Any]] = {}
        unit_seen: Dict[str, set] = {}

        for r in rows:
            p = r["pnu"]
            if p not in grouped:
                u_date = r.get("use_approval_date")
                grouped[p] = {
                    "pnu": p,
                    "buildingName": r.get("building_name"),
                    "buildingType": normalize_building_type_code(r.get("building_type")),
                    "adminDongCode": r.get("admin_dong_code"),
                    "adminDongName": r.get("admin_dong_name"),
                    "legalDongCode": r.get("legal_dong_code"),
                    "legalDongName": r.get("legal_dong_name"),
                    "jibunAddress": r.get("jibun_address"),
                    "totalHouseholds": r.get("total_households"),
                    "totalParking": r.get("total_parking"),
                    "useApprovalDate": u_date.isoformat() if u_date else None,
                    "unitTypes": []
                }
                unit_seen[p] = set()

            u_id = r.get("unit_id")
            if u_id and u_id not in unit_seen[p]:
                unit_seen[p].add(u_id)
                grouped[p]["unitTypes"].append(
                    UnitTypeItemDTO(
                        id=u_id,
                        exclusiveArea=float(r["exclusive_area"]) if r["exclusive_area"] is not None else 0.0,
                        pyungType=r.get("pyung_type") or 0,
                        householdCount=r.get("household_count") or 0
                    )
                )

        bld_items = [BuildingWithUnitsDTO(**v) for v in grouped.values()]
        return BuildingUnitsResponse(
            status=200,
            message="SUCCESS",
            data=BuildingUnitsData(totalBuildings=len(bld_items), items=bld_items)
        )
