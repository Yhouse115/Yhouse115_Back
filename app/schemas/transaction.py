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


# --- API #4: Rent List (/transactions/rents) ---
class RentItemDTO(BaseModel):
    rentId: str
    pnu: Optional[str] = None
    dealDate: Optional[str] = None
    rentType: Optional[str] = None
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
    deposit: Optional[int] = None
    monthlyRent: Optional[int] = None
    contractPeriod: Optional[str] = None
    useRrRight: Optional[str] = None


class RentListData(BaseModel):
    pagination: PaginationDTO
    items: List[RentItemDTO]


class RentListResponse(BaseModel):
    status: int = 200
    message: str = "SUCCESS"
    data: RentListData


# --- API #5: Development History (/developments) ---
class DevStageItemDTO(BaseModel):
    stageCode: str
    stageName: str
    eventDate: Optional[str] = None
    isCurrentStage: Optional[bool] = None
    isCompleted: Optional[bool] = None
    statusDetail: Optional[str] = None


class DevelopmentItemDTO(BaseModel):
    projectId: str
    pnu: Optional[str] = None
    projectName: str
    completedAptName: Optional[str] = None
    devType: Optional[str] = None
    targetHouseholds: Optional[int] = None
    adminDongCode: Optional[str] = None
    adminDongName: Optional[str] = None
    legalDongCode: Optional[str] = None
    legalDongName: Optional[str] = None
    address: Optional[str] = None
    jibunAddress: Optional[str] = None
    includedJibuns: List[str] = []
    includedPnus: List[str] = []
    includedApts: List[str] = []
    currentStage: Optional[DevStageItemDTO] = None
    history: List[DevStageItemDTO] = []


class DevelopmentListData(BaseModel):
    pagination: PaginationDTO
    items: List[DevelopmentItemDTO]


class DevelopmentListResponse(BaseModel):
    status: int = 200
    message: str = "SUCCESS"
    data: DevelopmentListData


# --- API #10: Development Detail (/developments/{project_id}) ---
class DevelopmentDetailResponse(BaseModel):
    status: int = 200
    message: str = "SUCCESS"
    data: Optional[DevelopmentItemDTO] = None



# --- API #6: Buildings List (/buildings) ---
class BuildingItemDTO(BaseModel):
    pnu: str
    buildingName: Optional[str] = None
    buildingType: Optional[str] = None
    adminDongCode: Optional[str] = None
    adminDongName: Optional[str] = None
    legalDongCode: Optional[str] = None
    legalDongName: Optional[str] = None
    jibunAddress: Optional[str] = None
    jibun: Optional[str] = None
    totalHouseholds: Optional[int] = None
    totalParking: Optional[int] = None
    useApprovalDate: Optional[str] = None
    buildYear: Optional[int] = None


class BuildingListData(BaseModel):
    pagination: PaginationDTO
    items: List[BuildingItemDTO]


class BuildingListResponse(BaseModel):
    status: int = 200
    message: str = "SUCCESS"
    data: BuildingListData


# --- API #7: Building Unit Types (/buildings/unit-types) ---
class UnitTypeItemDTO(BaseModel):
    id: int
    exclusiveArea: float
    pyungType: int
    householdCount: int


class BuildingWithUnitsDTO(BaseModel):
    pnu: str
    buildingName: Optional[str] = None
    buildingType: Optional[str] = None
    adminDongCode: Optional[str] = None
    adminDongName: Optional[str] = None
    legalDongCode: Optional[str] = None
    legalDongName: Optional[str] = None
    jibunAddress: Optional[str] = None
    totalHouseholds: Optional[int] = None
    totalParking: Optional[int] = None
    useApprovalDate: Optional[str] = None
    unitTypes: List[UnitTypeItemDTO] = []


class BuildingUnitsData(BaseModel):
    totalBuildings: int
    items: List[BuildingWithUnitsDTO]


class BuildingUnitsResponse(BaseModel):
    status: int = 200
    message: str = "SUCCESS"
    data: Optional[BuildingUnitsData] = None


# --- API #8: Building Detail Summary (/buildings/{pnu}/summary) ---
class BuildingInfoSummaryDTO(BaseModel):
    pnu: str
    buildingName: Optional[str] = None
    buildingType: Optional[str] = None
    adminDongCode: Optional[str] = None
    adminDongName: Optional[str] = None
    legalDongCode: Optional[str] = None
    legalDongName: Optional[str] = None
    jibunAddress: Optional[str] = None
    jibun: Optional[str] = None
    totalHouseholds: Optional[int] = None
    totalParking: Optional[int] = None
    parkingPerHousehold: Optional[float] = None
    useApprovalDate: Optional[str] = None
    buildYear: Optional[int] = None
    buildingAge: Optional[int] = None


class BuildingUnitTypeSummaryDTO(BaseModel):
    exclusiveArea: float
    pyungType: int
    householdCount: int
    recentTradePrice: Optional[int] = None
    priceChangeRate: Optional[float] = None
    pricePerPyeong: Optional[float] = None
    pricePerM2: Optional[float] = None
    maxTradePrice: Optional[int] = None
    minTradePrice: Optional[int] = None
    recentRentDeposit: Optional[int] = None
    jeonseRatio: Optional[float] = None


class BuildingPriceTrendItemDTO(BaseModel):
    yearMonth: str
    avgTradeAmount: Optional[int] = None
    tradeCount: int = 0
    avgRentDeposit: Optional[int] = None
    rentCount: int = 0


class BuildingRecentTradeItemDTO(BaseModel):
    id: str
    tradeType: str
    dealDate: str
    floor: Optional[int] = None
    exclArea: float
    dealAmount: Optional[int] = None
    monthlyRent: Optional[int] = None
    pricePerM2: Optional[float] = None


class BuildingDetailSummaryData(BaseModel):
    buildingInfo: BuildingInfoSummaryDTO
    unitTypes: List[BuildingUnitTypeSummaryDTO] = []
    recentTrades: List[BuildingRecentTradeItemDTO] = []
    priceTrends: List[BuildingPriceTrendItemDTO] = []


class BuildingDetailSummaryResponse(BaseModel):
    status: int = 200
    message: str = "SUCCESS"
    data: Optional[BuildingDetailSummaryData] = None


# --- API #9: Dong & Adjacent Dong Trends Summary (/summary/trends) ---
class DongUnitSizeStatDTO(BaseModel):
    category: str
    exclusiveAreaRange: str
    avgTradePrice: Optional[int] = None
    priceChangeRate: Optional[float] = None       # 매매 변동률 (전분기 또는 전년 동기 대비)
    medianPyeongPrice: Optional[float] = None
    medianPrice: Optional[int] = None
    minPrice: Optional[int] = None
    maxPrice: Optional[int] = None
    tradeCount: int = 0
    avgRentDeposit: Optional[int] = None          # 전세 평균 보증금
    rentChangeRate: Optional[float] = None        # 전세 변동률
    medianRentPyeongPrice: Optional[float] = None # 전세 평균 평단가
    rentCount: int = 0


class DongBaseStatsDTO(BaseModel):
    adminDongCode: str
    adminDongName: str
    avgTradePrice: Optional[int] = None
    medianTradePrice: Optional[int] = None
    priceChangeRate: Optional[float] = None
    medianPyeongPrice: Optional[float] = None
    avgRentDeposit: Optional[int] = None
    medianRentDeposit: Optional[int] = None
    rentChangeRate: Optional[float] = None
    medianRentPyeongPrice: Optional[float] = None
    jeonseRatio: Optional[float] = None
    unitSizeStats: List[DongUnitSizeStatDTO] = []


class AdjacentDongStatDTO(BaseModel):
    adminDongCode: str
    adminDongName: str
    avgTradePrice: Optional[int] = None
    medianPyeongPrice: Optional[float] = None
    priceChangeRate: Optional[float] = None
    avgRentDeposit: Optional[int] = None
    medianRentPyeongPrice: Optional[float] = None
    tradeCount: int = 0
    rentCount: int = 0


class DongTrendsSummaryData(BaseModel):
    adminDongCode: str
    adminDongName: str
    periodMonths: int
    comparisonMode: str                            # "prev_period" | "yoy"
    baseDongStats: DongBaseStatsDTO
    adjacentDongs: List[AdjacentDongStatDTO] = []
    adjacentAvgPyeongPrice: Optional[float] = None
    guAvgPyeongPrice: Optional[float] = None
    guPriceChangeRate: Optional[float] = None


class DongTrendsSummaryResponse(BaseModel):
    status: int = 200
    message: str = "SUCCESS"
    data: Optional[DongTrendsSummaryData] = None


# --- API #11: Region 1:1 Comparison Summary (/summary/region-comparison) ---
class RegionStatDTO(BaseModel):
    adminDongCode: str
    adminDongName: str
    avgTradePrice: Optional[int] = None
    medianTradePrice: Optional[int] = None
    medianPyeongPrice: Optional[float] = None
    priceChangeRate: Optional[float] = None
    avgRentDeposit: Optional[int] = None
    medianRentDeposit: Optional[int] = None
    medianRentPyeongPrice: Optional[float] = None
    rentChangeRate: Optional[float] = None
    jeonseRatio: Optional[float] = None
    tradeCount: int = 0
    rentCount: int = 0


class RegionComparisonSummaryDTO(BaseModel):
    priceDifference: Optional[int] = None
    pyeongPriceDifference: Optional[float] = None
    higherPyeongPriceRegion: str
    jeonseRatioDifference: Optional[float] = None


class RegionComparisonData(BaseModel):
    periodMonths: int
    baseRegion: RegionStatDTO
    targetRegion: RegionStatDTO
    comparisonSummary: RegionComparisonSummaryDTO


class RegionComparisonResponse(BaseModel):
    status: int = 200
    message: str = "SUCCESS"
    data: Optional[RegionComparisonData] = None



