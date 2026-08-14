from datetime import date
import math
from typing import Any, Dict, List, Optional
import re
import asyncpg

from fastapi import HTTPException, status

from app.repositories.transaction_repository import (
    TransactionRepository,
    normalize_building_type_code,
)
from app.schemas.transaction import (
    AdjacentDongStatDTO,
    BuildingDetailSummaryData,
    BuildingDetailSummaryResponse,
    BuildingInfoSummaryDTO,
    BuildingItemDTO,
    BuildingListData,
    BuildingListResponse,
    BuildingPnuResolutionData,
    BuildingPnuResolutionResponse,
    BuildingPriceTrendItemDTO,
    BuildingRecentTradeItemDTO,
    BuildingUnitTypeSummaryDTO,
    BuildingUnitsData,
    BuildingUnitsResponse,
    BuildingWithUnitsDTO,
    DevStageItemDTO,
    DevelopmentDetailResponse,
    DevelopmentItemDTO,
    DevelopmentListData,
    DevelopmentListResponse,

    DongBaseStatsDTO,
    DongTrendsSummaryData,
    DongTrendsSummaryResponse,
    DongUnitSizeStatDTO,

    InventoryItemDTO,
    InventorySummaryResponse,
    MonthlyTransactionSeriesItem,
    PaginationDTO,
    RegionComparisonData,
    RegionComparisonResponse,
    RegionComparisonSummaryDTO,
    RegionStatDTO,
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
    async def resolve_building_pnu(
        cls,
        conn: asyncpg.Connection,
        address: str,
        household_count: Optional[int],
    ) -> BuildingPnuResolutionResponse:
        # KREB complex address is a legal-dong lot address, e.g. "... 목동 901".
        matches = re.findall(r"([가-힣0-9]+(?:동|가|읍|면|리))\s+(\d+(?:-\d+)?)", address.strip())
        if not matches:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="INVALID_JIBUN_ADDRESS: 법정동과 지번을 주소에서 추출할 수 없습니다.",
            )

        legal_dong_name, jibun = matches[-1]
        rows = await TransactionRepository.resolve_building_pnu(
            conn, legal_dong_name, jibun, household_count
        )
        if not rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"BUILDING_PNU_NOT_FOUND: {legal_dong_name} {jibun}에 해당하는 건축물이 없습니다.",
            )

        if len(rows) > 1:
            exact_households = [
                row for row in rows
                if household_count is not None and row.get("total_households") == household_count
            ]
            if len(exact_households) == 1:
                row = exact_households[0]
                match_method = "legal_dong_jibun_households"
            else:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"AMBIGUOUS_BUILDING_PNU: {legal_dong_name} {jibun}의 PNU 후보가 여러 개입니다.",
                )
        else:
            row = rows[0]
            match_method = "legal_dong_jibun"

        return BuildingPnuResolutionResponse(
            data=BuildingPnuResolutionData(
                pnu=row["pnu"],
                buildingName=row.get("property_name"),
                legalDongName=legal_dong_name,
                jibun=jibun,
                matchMethod=match_method,
            )
        )


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
        pnu: Optional[str],
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
            conn, admin_dong_code, pnu, period_start, period_end, bld_types,
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
        pnu: Optional[str],
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
            conn, admin_dong_code, pnu, period_start, period_end, rent_type, bld_types,
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
    async def get_development_detail(
        cls,
        conn: asyncpg.Connection,
        project_id: str
    ) -> DevelopmentDetailResponse:
        rows = await TransactionRepository.get_development_detail(conn, project_id)
        if not rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"DEVELOPMENT_NOT_FOUND: 식별자({project_id})에 해당하는 정비사업 구역 데이터를 찾을 수 없습니다."
            )

        base_r = rows[0]
        rep_pnu = base_r.get("pnu") or ""
        pkey = rep_pnu or base_r.get("project_name") or ""
        res_proj_id = f"DEV_{rep_pnu}" if rep_pnu else (project_id if project_id.startswith("DEV_") else f"DEV_{abs(hash(pkey))}")

        curr_stage_dto = None
        history_dtos = []

        for r in rows:
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

        item_dto = DevelopmentItemDTO(
            projectId=res_proj_id,
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

        return DevelopmentDetailResponse(status=200, message="SUCCESS", data=item_dto)


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
            u_str = u_date.isoformat() if hasattr(u_date, "isoformat") else (str(u_date) if u_date else None)
            b_year = u_date.year if hasattr(u_date, "year") else (int(str(u_date)[:4]) if (u_date and str(u_date)[:4].isdigit()) else None)

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

    @classmethod
    async def get_building_detail_summary(
        cls,
        conn: asyncpg.Connection,
        pnu: str
    ) -> BuildingDetailSummaryResponse:
        result = await TransactionRepository.get_building_detail_summary(conn, pnu)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"BUILDING_NOT_FOUND: PNU({pnu})에 해당하는 건축물/단지 데이터를 찾을 수 없습니다."
            )

        info = result["building_info"]
        unit_types_raw = result["unit_types"]
        trades = result["trades"]
        rents = result["rents"]
        price_trends_raw = result["price_trends"]

        # 1. Building Info DTO
        tot_house = info.get("total_households")
        tot_park = info.get("total_parking")
        park_per_house = round(tot_park / tot_house, 2) if (tot_park and tot_house and tot_house > 0) else None

        use_app_date = info.get("use_approval_date")
        build_year = None
        building_age = None
        if use_app_date:
            try:
                b_year_str = use_app_date.split("-")[0] if "-" in use_app_date else use_app_date[:4]
                build_year = int(b_year_str)
                building_age = max(2026 - build_year + 1, 1)
            except Exception:
                pass

        b_info_dto = BuildingInfoSummaryDTO(
            pnu=info["pnu"],
            buildingName=info.get("building_name"),
            buildingType=normalize_building_type_code(info.get("building_type")),
            adminDongCode=info.get("admin_dong_code"),
            adminDongName=info.get("admin_dong_name"),
            legalDongCode=info.get("legal_dong_code"),
            legalDongName=info.get("legal_dong_name"),
            jibunAddress=info.get("jibun_address"),
            jibun=info.get("jibun"),
            totalHouseholds=tot_house,
            totalParking=tot_park,
            parkingPerHousehold=park_per_house,
            useApprovalDate=use_app_date,
            buildYear=build_year,
            buildingAge=building_age
        )

        # 2. Unit Types Summary DTOs
        unit_type_dtos = []
        all_excl_areas = [float(ut["exclusive_area"]) for ut in unit_types_raw]

        for ut in unit_types_raw:
            excl = float(ut["exclusive_area"])
            pyung = int(ut["pyung_type"])
            hh_cnt = int(ut["household_count"])

            # 거래의 전용면적이 속하는 가장 가까운 단일 평형으로만 고유 매칭 (84.96과 84.98 중복 방지)
            matching_trades = [
                t for t in trades
                if min(all_excl_areas, key=lambda a: abs(a - float(t["excl_area"]))) == excl
                   and abs(float(t["excl_area"]) - excl) <= 1.0
            ]
            matching_rents = [
                r for r in rents
                if min(all_excl_areas, key=lambda a: abs(a - float(r["excl_area"]))) == excl
                   and abs(float(r["excl_area"]) - excl) <= 1.0
                   and (
                       str(r.get("trade_type") or "").strip().upper() in ("전세", "JEONSE")
                       or ((r.get("monthly_rent") or 0) == 0 and (r.get("deal_amount") or 0) > 0)
                   )
            ]

            recent_trade_price = matching_trades[0]["deal_amount"] if matching_trades else None
            price_change_rate = None
            if len(matching_trades) >= 2 and matching_trades[1]["deal_amount"]:
                prev = matching_trades[1]["deal_amount"]
                curr = matching_trades[0]["deal_amount"]
                if prev > 0:
                    price_change_rate = round(((curr - prev) / prev) * 100, 1)

            price_per_pyeong = None
            price_per_m2 = None
            if recent_trade_price and excl > 0:
                pyeong = excl / 3.30578
                price_per_pyeong = round(recent_trade_price / pyeong, 1)
                price_per_m2 = round(recent_trade_price / excl, 1)

            max_trade_price = max([t["deal_amount"] for t in matching_trades if t.get("deal_amount")], default=None)
            min_trade_price = min([t["deal_amount"] for t in matching_trades if t.get("deal_amount")], default=None)

            recent_rent_deposit = matching_rents[0]["deal_amount"] if matching_rents else None
            jeonse_ratio = None
            if recent_rent_deposit and recent_trade_price and recent_trade_price > 0:
                jeonse_ratio = round((recent_rent_deposit / recent_trade_price) * 100, 1)

            unit_type_dtos.append(
                BuildingUnitTypeSummaryDTO(
                    exclusiveArea=excl,
                    pyungType=pyung,
                    householdCount=hh_cnt,
                    recentTradePrice=recent_trade_price,
                    priceChangeRate=price_change_rate,
                    pricePerPyeong=price_per_pyeong,
                    pricePerM2=price_per_m2,
                    maxTradePrice=max_trade_price,
                    minTradePrice=min_trade_price,
                    recentRentDeposit=recent_rent_deposit,
                    jeonseRatio=jeonse_ratio
                )
            )

        # 3. 건축물의 전체 거래 DTOs. 프런트의 기간 차트와 거래내역 페이지가
        # 같은 배열을 사용하므로 임의로 최신 50건만 자르지 않는다.
        combined_all = []
        for t in trades:
            combined_all.append({
                "id": f"TR_{t['id']}",
                "tradeType": "TRADE",
                "dealDate": t["deal_date"],
                "floor": t.get("floor"),
                "exclArea": float(t["excl_area"]),
                "dealAmount": t.get("deal_amount"),
                "monthlyRent": None,
                "pricePerM2": float(t["price_per_m2"]) if t.get("price_per_m2") else None
            })
        for r in rents:
            rent_type = str(r.get("trade_type") or "").strip().upper()
            if rent_type in ("전세", "JEONSE"):
                r_type = "JEONSE"
            elif rent_type in ("월세", "MONTHLY") or (r.get("monthly_rent") or 0) > 0:
                r_type = "MONTHLY"
            else:
                r_type = rent_type
            combined_all.append({
                "id": f"RN_{r['id']}",
                "tradeType": r_type,
                "dealDate": r["deal_date"],
                "floor": r.get("floor"),
                "exclArea": float(r["excl_area"]),
                "dealAmount": r.get("deal_amount"),
                "monthlyRent": r.get("monthly_rent"),
                "pricePerM2": None
            })

        combined_all.sort(key=lambda x: x["dealDate"], reverse=True)
        recent_trades_dtos = [BuildingRecentTradeItemDTO(**item) for item in combined_all]

        # 4. Price Trends DTOs
        trend_dtos = [
            BuildingPriceTrendItemDTO(
                yearMonth=pt["year_month"],
                avgTradeAmount=pt.get("avg_trade_amount"),
                tradeCount=pt.get("trade_count", 0),
                avgRentDeposit=pt.get("avg_rent_deposit"),
                rentCount=pt.get("rent_count", 0)
            ) for pt in price_trends_raw
        ]

        summary_data = BuildingDetailSummaryData(
            buildingInfo=b_info_dto,
            unitTypes=unit_type_dtos,
            recentTrades=recent_trades_dtos,
            priceTrends=trend_dtos
        )

        return BuildingDetailSummaryResponse(status=200, message="SUCCESS", data=summary_data)

    @classmethod
    async def get_dong_trends_summary(
        cls,
        conn: asyncpg.Connection,
        admin_dong_code: str,
        period_months: int = 3,
        raw_bld_types: Optional[List[str]] = None,
        include_adjacent: bool = True,
        comparison_mode: str = "prev_period"  # "prev_period" | "yoy"
    ) -> DongTrendsSummaryResponse:
        bld_types = None
        if raw_bld_types:
            bld_types = [normalize_building_type_code(b.strip()) for b in raw_bld_types if b.strip()]

        result = await TransactionRepository.get_dong_trends_summary(
            conn, admin_dong_code, period_months, bld_types, comparison_mode
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"DONG_NOT_FOUND: 행정동 코드({admin_dong_code})에 해당하는 데이터를 찾을 수 없습니다."
            )

        base_info = result["base_info"]
        adj_info_rows = result["adj_info_rows"]
        b_trades_curr = result["base_trades_curr"]
        b_trades_prev = result["base_trades_prev"]
        b_rents_curr = result["base_rents_curr"]
        b_rents_prev = result["base_rents_prev"]
        adj_trades_map = result["adj_trades_map"]
        adj_rents_map = result["adj_rents_map"]
        gu_trades_curr = result["gu_trades_curr"]
        gu_trades_prev = result["gu_trades_prev"]

        def calc_avg(amounts: List[int]) -> Optional[int]:
            return round(sum(amounts) / len(amounts)) if amounts else None

        def calc_median(amounts: List[float]) -> Optional[float]:
            if not amounts:
                return None
            sorted_arr = sorted(amounts)
            n = len(sorted_arr)
            mid = n // 2
            if n % 2 == 1:
                return sorted_arr[mid]
            return (sorted_arr[mid - 1] + sorted_arr[mid]) / 2.0

        def calc_change_rate(curr_avg: Optional[float], prev_avg: Optional[float]) -> Optional[float]:
            if curr_avg and prev_avg and prev_avg > 0:
                return round(((curr_avg - prev_avg) / prev_avg) * 100, 1)
            return None

        # 1. Base dong overall stats
        b_trade_amounts_curr = [t["deal_amount"] for t in b_trades_curr if t.get("deal_amount")]
        b_trade_amounts_prev = [t["deal_amount"] for t in b_trades_prev if t.get("deal_amount")]

        b_trade_pyeongs_curr = [
            t["deal_amount"] / (float(t["excl_area"]) / 3.30578)
            for t in b_trades_curr
            if t.get("deal_amount") and t.get("excl_area") and float(t["excl_area"]) > 0
        ]

        b_rent_amounts_curr = [r["deposit"] for r in b_rents_curr if r.get("deposit")]
        b_rent_amounts_prev = [r["deposit"] for r in b_rents_prev if r.get("deposit")]

        b_rent_pyeongs_curr = [
            r["deposit"] / (float(r["excl_area"]) / 3.30578)
            for r in b_rents_curr
            if r.get("deposit") and r.get("excl_area") and float(r["excl_area"]) > 0
        ]

        avg_trade_price = calc_avg(b_trade_amounts_curr)
        prev_avg_trade = calc_avg(b_trade_amounts_prev)
        price_change_rate = calc_change_rate(avg_trade_price, prev_avg_trade)
        median_trade_price = round(calc_median(b_trade_amounts_curr)) if calc_median(b_trade_amounts_curr) else None
        median_pyeong_price = round(calc_median(b_trade_pyeongs_curr), 1) if calc_median(b_trade_pyeongs_curr) else None

        avg_rent_deposit = calc_avg(b_rent_amounts_curr)
        prev_avg_rent = calc_avg(b_rent_amounts_prev)
        rent_change_rate = calc_change_rate(avg_rent_deposit, prev_avg_rent)
        median_rent_deposit = round(calc_median(b_rent_amounts_curr)) if calc_median(b_rent_amounts_curr) else None
        median_rent_pyeong_price = round(calc_median(b_rent_pyeongs_curr), 1) if calc_median(b_rent_pyeongs_curr) else None

        jeonse_ratio = None
        if avg_rent_deposit and avg_trade_price and avg_trade_price > 0:
            jeonse_ratio = round((avg_rent_deposit / avg_trade_price) * 100, 1)

        # 2. Base dong unit size categories (소형, 중형, 대형)
        categories = [
            ("소형", "(60㎡ 이하)", lambda a: a <= 60.0),
            ("중형", "(60~85㎡)", lambda a: 60.0 < a <= 85.0),
            ("대형", "(85㎡ 초과)", lambda a: a > 85.0)
        ]

        unit_size_dtos = []
        for cat_name, cat_range, cat_filter in categories:
            cat_trades_curr = [t for t in b_trades_curr if t.get("excl_area") and cat_filter(float(t["excl_area"]))]
            cat_trades_prev = [t for t in b_trades_prev if t.get("excl_area") and cat_filter(float(t["excl_area"]))]

            # 매매 지표
            cat_amounts_curr = [t["deal_amount"] for t in cat_trades_curr if t.get("deal_amount")]
            cat_amounts_prev = [t["deal_amount"] for t in cat_trades_prev if t.get("deal_amount")]
            cat_pyeongs_curr = [
                t["deal_amount"] / (float(t["excl_area"]) / 3.30578)
                for t in cat_trades_curr
                if t.get("deal_amount") and t.get("excl_area") and float(t["excl_area"]) > 0
            ]

            c_avg = calc_avg(cat_amounts_curr)
            c_prev_avg = calc_avg(cat_amounts_prev)
            c_change = calc_change_rate(c_avg, c_prev_avg)
            c_med = round(calc_median(cat_amounts_curr)) if calc_median(cat_amounts_curr) else None
            c_med_pyeong = round(calc_median(cat_pyeongs_curr), 1) if calc_median(cat_pyeongs_curr) else None
            c_min = min(cat_amounts_curr, default=None)
            c_max = max(cat_amounts_curr, default=None)

            # 전세 지표 (전세만 필터)
            cat_jeonse_curr = [
                r for r in b_rents_curr
                if r.get("excl_area") and cat_filter(float(r["excl_area"]))
                and r.get("rent_type") in ("JEONSE", "jeonse", "J")
            ]
            cat_jeonse_prev = [
                r for r in b_rents_prev
                if r.get("excl_area") and cat_filter(float(r["excl_area"]))
                and r.get("rent_type") in ("JEONSE", "jeonse", "J")
            ]
            j_amounts_curr = [r["deposit"] for r in cat_jeonse_curr if r.get("deposit")]
            j_amounts_prev = [r["deposit"] for r in cat_jeonse_prev if r.get("deposit")]
            j_pyeongs_curr = [
                r["deposit"] / (float(r["excl_area"]) / 3.30578)
                for r in cat_jeonse_curr
                if r.get("deposit") and r.get("excl_area") and float(r["excl_area"]) > 0
            ]
            j_avg = calc_avg(j_amounts_curr)
            j_prev_avg = calc_avg(j_amounts_prev)
            j_change = calc_change_rate(j_avg, j_prev_avg)
            j_med_pyeong = round(calc_median(j_pyeongs_curr), 1) if calc_median(j_pyeongs_curr) else None

            unit_size_dtos.append(
                DongUnitSizeStatDTO(
                    category=cat_name,
                    exclusiveAreaRange=cat_range,
                    avgTradePrice=c_avg,
                    priceChangeRate=c_change,
                    medianPyeongPrice=c_med_pyeong,
                    medianPrice=c_med,
                    minPrice=c_min,
                    maxPrice=c_max,
                    tradeCount=len(cat_trades_curr),
                    avgRentDeposit=j_avg,
                    rentChangeRate=j_change,
                    medianRentPyeongPrice=j_med_pyeong,
                    rentCount=len(cat_jeonse_curr)
                )
            )

        base_dong_stats = DongBaseStatsDTO(
            adminDongCode=admin_dong_code,
            adminDongName=base_info.get("admin_dong_name") or "",
            avgTradePrice=avg_trade_price,
            medianTradePrice=median_trade_price,
            priceChangeRate=price_change_rate,
            medianPyeongPrice=median_pyeong_price,
            avgRentDeposit=avg_rent_deposit,
            medianRentDeposit=median_rent_deposit,
            rentChangeRate=rent_change_rate,
            medianRentPyeongPrice=median_rent_pyeong_price,
            jeonseRatio=jeonse_ratio,
            unitSizeStats=unit_size_dtos
        )

        # 3. Adjacent Dongs Stats
        adjacent_dtos = []
        all_adj_pyeongs = []
        if include_adjacent:
            for adj_info in adj_info_rows:
                code = adj_info["admin_dong_code"]
                name = adj_info["admin_dong_name"]

                a_trades = adj_trades_map.get(code, [])
                a_rents = adj_rents_map.get(code, [])

                a_trade_amounts = [t["deal_amount"] for t in a_trades if t.get("deal_amount")]
                a_trade_pyeongs = [
                    t["deal_amount"] / (float(t["excl_area"]) / 3.30578)
                    for t in a_trades
                    if t.get("deal_amount") and t.get("excl_area") and float(t["excl_area"]) > 0
                ]
                all_adj_pyeongs.extend(a_trade_pyeongs)

                a_rent_deposits = [r["deposit"] for r in a_rents if r.get("deposit")]
                a_rent_pyeongs = [
                    r["deposit"] / (float(r["excl_area"]) / 3.30578)
                    for r in a_rents
                    if r.get("deposit") and r.get("excl_area") and float(r["excl_area"]) > 0
                ]

                a_avg_trade = calc_avg(a_trade_amounts)
                a_med_pyeong = round(calc_median(a_trade_pyeongs), 1) if calc_median(a_trade_pyeongs) else None
                a_avg_rent = calc_avg(a_rent_deposits)
                a_rent_med_pyeong = round(calc_median(a_rent_pyeongs), 1) if calc_median(a_rent_pyeongs) else None

                adjacent_dtos.append(
                    AdjacentDongStatDTO(
                        adminDongCode=code,
                        adminDongName=name,
                        avgTradePrice=a_avg_trade,
                        medianPyeongPrice=a_med_pyeong,
                        priceChangeRate=None,
                        avgRentDeposit=a_avg_rent,
                        medianRentPyeongPrice=a_rent_med_pyeong,
                        tradeCount=len(a_trades),
                        rentCount=len(a_rents)
                    )
                )

        adj_avg_pyeong_price = round(calc_median(all_adj_pyeongs), 1) if calc_median(all_adj_pyeongs) else None

        # 4. Gu level stats
        gu_curr_pyeongs = [
            t["deal_amount"] / (float(t["excl_area"]) / 3.30578)
            for t in gu_trades_curr
            if t.get("deal_amount") and t.get("excl_area") and float(t["excl_area"]) > 0
        ]
        gu_prev_pyeongs = [
            t["deal_amount"] / (float(t["excl_area"]) / 3.30578)
            for t in gu_trades_prev
            if t.get("deal_amount") and t.get("excl_area") and float(t["excl_area"]) > 0
        ]

        gu_med_pyeong = round(calc_median(gu_curr_pyeongs), 1) if calc_median(gu_curr_pyeongs) else None
        gu_prev_med_pyeong = calc_median(gu_prev_pyeongs)
        gu_change_rate = calc_change_rate(gu_med_pyeong, gu_prev_med_pyeong)

        summary_data = DongTrendsSummaryData(
            adminDongCode=admin_dong_code,
            adminDongName=base_info.get("admin_dong_name") or "",
            periodMonths=period_months,
            comparisonMode=result.get("comparison_mode", "prev_period"),
            baseDongStats=base_dong_stats,
            adjacentDongs=adjacent_dtos,
            adjacentAvgPyeongPrice=adj_avg_pyeong_price,
            guAvgPyeongPrice=gu_med_pyeong,
            guPriceChangeRate=gu_change_rate
        )

        return DongTrendsSummaryResponse(status=200, message="SUCCESS", data=summary_data)

    @classmethod
    async def get_region_comparison(
        cls,
        conn: asyncpg.Connection,
        base_admin_dong_code: str,
        target_admin_dong_code: str,
        period_months: int = 3
    ) -> RegionComparisonResponse:
        base_raw = await TransactionRepository.get_region_stat(conn, base_admin_dong_code, period_months)
        target_raw = await TransactionRepository.get_region_stat(conn, target_admin_dong_code, period_months)

        if not base_raw:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"BASE_DONG_NOT_FOUND: 기준 행정동 코드({base_admin_dong_code})에 해당하는 데이터를 찾을 수 없습니다."
            )
        if not target_raw:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"TARGET_DONG_NOT_FOUND: 비교 대상 행정동 코드({target_admin_dong_code})에 해당하는 데이터를 찾을 수 없습니다."
            )

        def build_region_dto(raw_data: Dict[str, Any], code: str) -> RegionStatDTO:
            info = raw_data["dong_info"]
            t_curr = raw_data["trades_curr"]
            t_prev = raw_data["trades_prev"]
            r_curr = raw_data["rents_curr"]
            r_prev = raw_data["rents_prev"]

            t_amt_curr = [t["deal_amount"] for t in t_curr if t.get("deal_amount")]
            t_amt_prev = [t["deal_amount"] for t in t_prev if t.get("deal_amount")]
            t_pyeongs_curr = [
                t["deal_amount"] / (float(t["excl_area"]) / 3.30578)
                for t in t_curr
                if t.get("deal_amount") and t.get("excl_area") and float(t["excl_area"]) > 0
            ]

            r_amt_curr = [r["deposit"] for r in r_curr if r.get("deposit")]
            r_amt_prev = [r["deposit"] for r in r_prev if r.get("deposit")]
            r_pyeongs_curr = [
                r["deposit"] / (float(r["excl_area"]) / 3.30578)
                for r in r_curr
                if r.get("deposit") and r.get("excl_area") and float(r["excl_area"]) > 0
            ]

            avg_t = round(sum(t_amt_curr) / len(t_amt_curr)) if t_amt_curr else None
            prev_avg_t = round(sum(t_amt_prev) / len(t_amt_prev)) if t_amt_prev else None
            change_t = round(((avg_t - prev_avg_t) / prev_avg_t) * 100, 1) if (avg_t and prev_avg_t and prev_avg_t > 0) else None

            med_t = None
            if t_amt_curr:
                s_t = sorted(t_amt_curr)
                mid_idx = len(s_t) // 2
                med_t = s_t[mid_idx] if len(s_t) % 2 == 1 else round((s_t[mid_idx - 1] + s_t[mid_idx]) / 2)

            med_pyeong_t = None
            if t_pyeongs_curr:
                s_p = sorted(t_pyeongs_curr)
                mid_idx = len(s_p) // 2
                val_p = s_p[mid_idx] if len(s_p) % 2 == 1 else (s_p[mid_idx - 1] + s_p[mid_idx]) / 2.0
                med_pyeong_t = round(val_p, 1)

            avg_r = round(sum(r_amt_curr) / len(r_amt_curr)) if r_amt_curr else None
            prev_avg_r = round(sum(r_amt_prev) / len(r_amt_prev)) if r_amt_prev else None
            change_r = round(((avg_r - prev_avg_r) / prev_avg_r) * 100, 1) if (avg_r and prev_avg_r and prev_avg_r > 0) else None

            med_r = None
            if r_amt_curr:
                s_r = sorted(r_amt_curr)
                mid_idx = len(s_r) // 2
                med_r = s_r[mid_idx] if len(s_r) % 2 == 1 else round((s_r[mid_idx - 1] + s_r[mid_idx]) / 2)

            med_pyeong_r = None
            if r_pyeongs_curr:
                s_rp = sorted(r_pyeongs_curr)
                mid_idx = len(s_rp) // 2
                val_rp = s_rp[mid_idx] if len(s_rp) % 2 == 1 else (s_rp[mid_idx - 1] + s_rp[mid_idx]) / 2.0
                med_pyeong_r = round(val_rp, 1)

            jeonse_r = round((avg_r / avg_t) * 100, 1) if (avg_r and avg_t and avg_t > 0) else None

            return RegionStatDTO(
                adminDongCode=code,
                adminDongName=info.get("admin_dong_name") or "",
                avgTradePrice=avg_t,
                medianTradePrice=med_t,
                medianPyeongPrice=med_pyeong_t,
                priceChangeRate=change_t,
                avgRentDeposit=avg_r,
                medianRentDeposit=med_r,
                medianRentPyeongPrice=med_pyeong_r,
                rentChangeRate=change_r,
                jeonseRatio=jeonse_r,
                tradeCount=len(t_curr),
                rentCount=len(r_curr)
            )

        base_dto = build_region_dto(base_raw, base_admin_dong_code)
        target_dto = build_region_dto(target_raw, target_admin_dong_code)

        price_diff = None
        if base_dto.avgTradePrice is not None and target_dto.avgTradePrice is not None:
            price_diff = base_dto.avgTradePrice - target_dto.avgTradePrice

        pyeong_diff = None
        higher_region = "EQUAL"
        if base_dto.medianPyeongPrice is not None and target_dto.medianPyeongPrice is not None:
            pyeong_diff = round(base_dto.medianPyeongPrice - target_dto.medianPyeongPrice, 1)
            if pyeong_diff > 0:
                higher_region = "BASE"
            elif pyeong_diff < 0:
                higher_region = "TARGET"

        jeonse_diff = None
        if base_dto.jeonseRatio is not None and target_dto.jeonseRatio is not None:
            jeonse_diff = round(base_dto.jeonseRatio - target_dto.jeonseRatio, 1)

        summary_dto = RegionComparisonSummaryDTO(
            priceDifference=price_diff,
            pyeongPriceDifference=pyeong_diff,
            higherPyeongPriceRegion=higher_region,
            jeonseRatioDifference=jeonse_diff
        )

        data = RegionComparisonData(
            periodMonths=period_months,
            baseRegion=base_dto,
            targetRegion=target_dto,
            comparisonSummary=summary_dto
        )

        return RegionComparisonResponse(status=200, message="SUCCESS", data=data)
