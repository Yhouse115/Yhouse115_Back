-- Migration: 20260812000000_create_domain_tables.sql
-- Create initial domain tables for WhyHouse data (.me CSV imports)

-- 1. admin_dong_adjacencies
CREATE TABLE IF NOT EXISTS public.admin_dong_adjacencies (
    admin_dong_code VARCHAR(10) PRIMARY KEY,
    admin_dong_name VARCHAR(50) NOT NULL,
    legal_dong_name VARCHAR(50) NOT NULL,
    adjacent_dong_codes TEXT,
    adjacent_dong_names TEXT
);

-- 2. residential_buildings
CREATE TABLE IF NOT EXISTS public.residential_buildings (
    pnu VARCHAR(19) PRIMARY KEY,
    property_name VARCHAR(255),
    jibun_address VARCHAR(255),
    legal_dong_name VARCHAR(50),
    legal_dong_code VARCHAR(10),
    admin_dong_name VARCHAR(50),
    admin_dong_code VARCHAR(10),
    jibun VARCHAR(50),
    property_category VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_res_bld_admin_dong ON public.residential_buildings (admin_dong_code);
CREATE INDEX IF NOT EXISTS idx_res_bld_category ON public.residential_buildings (property_category);

-- 3. history_developments
CREATE TABLE IF NOT EXISTS public.history_developments (
    id BIGSERIAL PRIMARY KEY,
    pnu VARCHAR(19),
    jibun_address VARCHAR(255),
    project_name VARCHAR(255),
    completed_apt_name VARCHAR(255),
    included_jibuns TEXT,
    included_pnus TEXT,
    included_apts TEXT,
    stage_code VARCHAR(50),
    stage_name VARCHAR(100),
    event_date DATE,
    is_current_stage BOOLEAN DEFAULT FALSE,
    is_completed BOOLEAN DEFAULT FALSE,
    status_detail TEXT,
    dev_type VARCHAR(50),
    target_households INTEGER,
    address VARCHAR(255),
    legal_dong_name VARCHAR(50),
    legal_dong_code VARCHAR(10),
    admin_dong_name VARCHAR(50),
    admin_dong_code VARCHAR(10),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_hist_dev_pnu ON public.history_developments (pnu);
CREATE INDEX IF NOT EXISTS idx_hist_dev_admin_dong ON public.history_developments (admin_dong_code);

-- 4. transaction_rents
CREATE TABLE IF NOT EXISTS public.transaction_rents (
    id BIGSERIAL PRIMARY KEY,
    pnu VARCHAR(19),
    jibun_address VARCHAR(255),
    house_type VARCHAR(50),
    deal_date DATE,
    apt_name VARCHAR(255),
    legal_dong_name VARCHAR(50),
    legal_dong_code VARCHAR(10),
    admin_dong_name VARCHAR(50),
    admin_dong_code VARCHAR(10),
    jibun VARCHAR(50),
    rent_type VARCHAR(20),
    deposit BIGINT,
    monthly_rent BIGINT,
    excl_area NUMERIC(10, 2),
    floor INTEGER,
    contract_period VARCHAR(50),
    use_rr_right VARCHAR(50)
);

CREATE INDEX IF NOT EXISTS idx_tx_rents_pnu ON public.transaction_rents (pnu);
CREATE INDEX IF NOT EXISTS idx_tx_rents_deal_date ON public.transaction_rents (deal_date);
CREATE INDEX IF NOT EXISTS idx_tx_rents_admin_dong ON public.transaction_rents (admin_dong_code);

-- 5. transaction_trades
CREATE TABLE IF NOT EXISTS public.transaction_trades (
    id BIGSERIAL PRIMARY KEY,
    pnu VARCHAR(19),
    jibun_address VARCHAR(255),
    house_type VARCHAR(50),
    deal_date DATE,
    apt_name VARCHAR(255),
    legal_dong_name VARCHAR(50),
    legal_dong_code VARCHAR(10),
    admin_dong_name VARCHAR(50),
    admin_dong_code VARCHAR(10),
    jibun VARCHAR(50),
    excl_area NUMERIC(10, 2),
    floor INTEGER,
    deal_amount BIGINT,
    price_per_m2 NUMERIC(12, 2),
    build_year INTEGER,
    cancel_deal_day VARCHAR(50)
);

CREATE INDEX IF NOT EXISTS idx_tx_trades_pnu ON public.transaction_trades (pnu);
CREATE INDEX IF NOT EXISTS idx_tx_trades_deal_date ON public.transaction_trades (deal_date);
CREATE INDEX IF NOT EXISTS idx_tx_trades_admin_dong ON public.transaction_trades (admin_dong_code);
