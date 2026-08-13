# API Contract Document

본 문서는 WhyHouse 백엔드의 REST API 계약(API Contract) 명세서입니다.

---

## 📌 주요 REST API 목록 (API #1 ~ API #7)

### 1. `GET /summary/inventory`
- **설명**: 행정동 내 주거 부동산 유형(아파트, 연립다세대, 오피스텔) 재고 구성 수량 조회
- **파라미터**: `admin_dong_code` (행정동 10자리 코드, 필수)
- **응답 래퍼**: `InventorySummaryResponse`

### 2. `GET /summary/transaction-count`
- **설명**: 월별 거래유형(매매, 전세, 월세) $\times$ 건축물유형별 거래량 추이 조회
- **파라미터**: `admin_dong_code` (필수), `period_start`, `period_end`, `transaction_type`, `building_type`
- **응답 래퍼**: `TransactionCountResponse`

### 3. `GET /transactions/trades`
- **설명**: 매매 실거래가 리스트 조회 (가격, 면적, 단지명, 행정동 필터 및 페이지네이션)
- **파라미터**: `admin_dong_code`, `period_start`, `period_end`, `building_type`, `apt_name`, `min_deal_amount`, `max_deal_amount`, `min_excl_area`, `max_excl_area`, `page`, `size`, `sort`
- **응답 래퍼**: `TradeListResponse`

### 4. `GET /transactions/rents`
- **설명**: 전월세 실거래가 리스트 조회 (보증금, 월세금, 임대구분, 갱신권 필터 및 페이지네이션)
- **파라미터**: `admin_dong_code`, `period_start`, `period_end`, `rent_type`, `building_type`, `apt_name`, `min_deposit`, `max_deposit`, `min_monthly_rent`, `max_monthly_rent`, `min_excl_area`, `max_excl_area`, `page`, `size`, `sort`
- **응답 래퍼**: `RentListResponse`

### 5. `GET /developments`
- **설명**: 재개발/재건축 정비사업 이력 및 6단계 마일스톤 타임라인 조회
- **파라미터**: `admin_dong_code`, `dev_type`, `project_name`, `stage_code`, `is_completed`, `pnu`, `page`, `size`
- **응답 래퍼**: `DevelopmentListResponse`

### 6. `GET /buildings`
- **설명**: 동네 주거용 건축물(단지) 목록 조회
- **파라미터**: `admin_dong_code`, `building_type`, `building_name`, `page`, `size`
- **응답 래퍼**: `BuildingListResponse`

### 7. `GET /buildings/unit-types`
- **설명**: 건축물 단위 평형 타입 및 평형별 세대수 상세 조회 (평형 데이터 미존재 시 404 반환)
- **파라미터**: `pnu`, `building_name`, `admin_dong_code` (최소 1개 이상 필수)
- **응답 래퍼**: `BuildingUnitsResponse` (미존재 시 404 `UNIT_TYPES_NOT_FOUND`)

---

## ⚙️ 시스템 및 헬스 체크

### `GET /health` 및 `GET /api/v1/health`
- **설명**: 백엔드 시스템 헬스 체크 상태 반환 (`200 OK`)

### `GET /demo`
- **설명**: API #1 ~ #7 대화형 디버깅 및 테스팅 웹 페이지 제공
