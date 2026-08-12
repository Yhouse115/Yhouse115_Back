-- Migration unit 1: schema_changes
-- Transaction mode: transactional
-- Boundary reason: default

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES TO anon;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON SEQUENCES TO anon;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON ROUTINES TO anon;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES TO authenticated;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON SEQUENCES TO authenticated;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON ROUTINES TO authenticated;

CREATE SEQUENCE public.history_developments_id_seq;

CREATE SEQUENCE public.transaction_rents_id_seq;

CREATE SEQUENCE public.transaction_trades_id_seq;

CREATE TABLE public.admin_dong (
  admin_dong_code     character varying(10) NOT NULL,
  admin_dong_name     character varying(50) NOT NULL,
  legal_dong_name     character varying(50) NOT NULL,
  adjacent_dong_codes text,
  adjacent_dong_names text
);

ALTER TABLE public.admin_dong
  ADD CONSTRAINT admin_dong_adjacencies_pkey PRIMARY KEY (admin_dong_code);

GRANT ALL ON public.admin_dong TO anon;

GRANT ALL ON public.admin_dong TO authenticated;

GRANT ALL ON public.admin_dong TO service_role;

CREATE TABLE public.history_developments (
  id                 bigint                   DEFAULT nextval('public.history_developments_id_seq'::regclass) NOT NULL,
  pnu                character varying(19),
  jibun_address      character varying(255),
  project_name       character varying(255),
  completed_apt_name character varying(255),
  included_jibuns    text,
  included_pnus      text,
  included_apts      text,
  stage_code         character varying(50),
  stage_name         character varying(100),
  event_date         date,
  is_current_stage   boolean                  DEFAULT false,
  is_completed       boolean                  DEFAULT false,
  status_detail      text,
  dev_type           character varying(50),
  target_households  integer,
  address            character varying(255),
  legal_dong_name    character varying(50),
  legal_dong_code    character varying(10),
  admin_dong_name    character varying(50),
  admin_dong_code    character varying(10),
  created_at         timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);

ALTER SEQUENCE public.history_developments_id_seq OWNED BY public.history_developments.id;

GRANT ALL ON SEQUENCE public.history_developments_id_seq TO anon;

GRANT ALL ON SEQUENCE public.history_developments_id_seq TO authenticated;

GRANT ALL ON SEQUENCE public.history_developments_id_seq TO service_role;

ALTER TABLE public.history_developments
  ADD CONSTRAINT history_developments_pkey PRIMARY KEY (id);

GRANT ALL ON public.history_developments TO anon;

GRANT ALL ON public.history_developments TO authenticated;

GRANT ALL ON public.history_developments TO service_role;

CREATE INDEX idx_hist_dev_admin_dong ON public.history_developments (admin_dong_code);

CREATE INDEX idx_hist_dev_pnu ON public.history_developments (pnu);

CREATE TABLE public.residential_buildings (
  pnu               character varying(19)    NOT NULL,
  property_name     character varying(255),
  jibun_address     character varying(255),
  legal_dong_name   character varying(50),
  legal_dong_code   character varying(10),
  admin_dong_name   character varying(50),
  admin_dong_code   character varying(10),
  jibun             character varying(50),
  property_category character varying(50),
  created_at        timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE public.residential_buildings
  ADD CONSTRAINT residential_buildings_pkey PRIMARY KEY (pnu);

GRANT ALL ON public.residential_buildings TO anon;

GRANT ALL ON public.residential_buildings TO authenticated;

GRANT ALL ON public.residential_buildings TO service_role;

CREATE INDEX idx_res_bld_category ON public.residential_buildings (property_category);

CREATE INDEX idx_res_bld_admin_dong ON public.residential_buildings (admin_dong_code);

CREATE TABLE public.transaction_rents (
  id              bigint                 DEFAULT nextval('public.transaction_rents_id_seq'::regclass) NOT NULL,
  pnu             character varying(19),
  jibun_address   character varying(255),
  house_type      character varying(50),
  deal_date       date,
  apt_name        character varying(255),
  legal_dong_name character varying(50),
  legal_dong_code character varying(10),
  admin_dong_name character varying(50),
  admin_dong_code character varying(10),
  jibun           character varying(50),
  rent_type       character varying(20),
  deposit         bigint,
  monthly_rent    bigint,
  excl_area       numeric(10,2),
  floor           integer,
  contract_period character varying(50),
  use_rr_right    character varying(50)
);

ALTER SEQUENCE public.transaction_rents_id_seq OWNED BY public.transaction_rents.id;

GRANT ALL ON SEQUENCE public.transaction_rents_id_seq TO anon;

GRANT ALL ON SEQUENCE public.transaction_rents_id_seq TO authenticated;

GRANT ALL ON SEQUENCE public.transaction_rents_id_seq TO service_role;

ALTER TABLE public.transaction_rents
  ADD CONSTRAINT transaction_rents_pkey PRIMARY KEY (id);

GRANT ALL ON public.transaction_rents TO anon;

GRANT ALL ON public.transaction_rents TO authenticated;

GRANT ALL ON public.transaction_rents TO service_role;

CREATE INDEX idx_tx_rents_deal_date ON public.transaction_rents (deal_date);

CREATE INDEX idx_tx_rents_pnu ON public.transaction_rents (pnu);

CREATE INDEX idx_tx_rents_admin_dong ON public.transaction_rents (admin_dong_code);

CREATE TABLE public.transaction_trades (
  id              bigint                 DEFAULT nextval('public.transaction_trades_id_seq'::regclass) NOT NULL,
  pnu             character varying(19),
  jibun_address   character varying(255),
  house_type      character varying(50),
  deal_date       date,
  apt_name        character varying(255),
  legal_dong_name character varying(50),
  legal_dong_code character varying(10),
  admin_dong_name character varying(50),
  admin_dong_code character varying(10),
  jibun           character varying(50),
  excl_area       numeric(10,2),
  floor           integer,
  deal_amount     bigint,
  price_per_m2    numeric(12,2),
  build_year      integer,
  cancel_deal_day character varying(50)
);

ALTER SEQUENCE public.transaction_trades_id_seq OWNED BY public.transaction_trades.id;

GRANT ALL ON SEQUENCE public.transaction_trades_id_seq TO anon;

GRANT ALL ON SEQUENCE public.transaction_trades_id_seq TO authenticated;

GRANT ALL ON SEQUENCE public.transaction_trades_id_seq TO service_role;

ALTER TABLE public.transaction_trades
  ADD CONSTRAINT transaction_trades_pkey PRIMARY KEY (id);

GRANT ALL ON public.transaction_trades TO anon;

GRANT ALL ON public.transaction_trades TO authenticated;

GRANT ALL ON public.transaction_trades TO service_role;

CREATE INDEX idx_tx_trades_admin_dong ON public.transaction_trades (admin_dong_code);

CREATE INDEX idx_tx_trades_pnu ON public.transaction_trades (pnu);

CREATE INDEX idx_tx_trades_deal_date ON public.transaction_trades (deal_date);
