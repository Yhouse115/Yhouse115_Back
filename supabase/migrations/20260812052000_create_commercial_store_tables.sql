create table if not exists public.commercial_stores_seoul_raw (
    store_id text primary key,
    store_name text,
    branch_name text,
    category_large_code text,
    category_large_name text,
    category_medium_code text,
    category_medium_name text,
    category_small_code text,
    category_small_name text,
    standard_industry_code text,
    standard_industry_name text,
    sido_code text,
    sido_name text,
    sigungu_code text,
    sigungu_name text,
    admin_dong_code text,
    admin_dong_name text,
    legal_dong_code text,
    legal_dong_name text,
    lot_code text,
    land_type_code text,
    land_type_name text,
    lot_main_number text,
    lot_sub_number text,
    lot_address text,
    road_code text,
    road_name text,
    building_main_number text,
    building_sub_number text,
    building_management_number text,
    building_name text,
    road_address text,
    old_postal_code text,
    new_postal_code text,
    dong_info text,
    floor_info text,
    room_info text,
    longitude double precision,
    latitude double precision,
    source_year_month text not null default '202606',
    loaded_at timestamptz not null default now()
);

create index if not exists commercial_stores_seoul_raw_sigungu_idx
    on public.commercial_stores_seoul_raw (sigungu_name);

create index if not exists commercial_stores_seoul_raw_admin_dong_idx
    on public.commercial_stores_seoul_raw (admin_dong_name);

create index if not exists commercial_stores_seoul_raw_category_idx
    on public.commercial_stores_seoul_raw (
        category_large_name,
        category_medium_name,
        category_small_name
    );

create index if not exists commercial_stores_seoul_raw_lon_lat_idx
    on public.commercial_stores_seoul_raw (longitude, latitude);

alter table public.commercial_stores_seoul_raw enable row level security;

create table if not exists public.commercial_stores_yangcheon_processed (
    store_id text primary key,
    store_name text not null,
    branch_name text,
    display_name text not null,
    category_large_name text,
    category_medium_name text,
    category_small_name text,
    industry_name text,
    sido_name text not null default '서울특별시',
    sigungu_name text not null default '양천구',
    admin_dong_name text,
    legal_dong_name text,
    road_address text,
    lot_address text,
    building_name text,
    floor_info text,
    longitude double precision not null,
    latitude double precision not null,
    source_year_month text not null default '202606',
    processed_at timestamptz not null default now()
);

create index if not exists commercial_stores_yangcheon_admin_dong_idx
    on public.commercial_stores_yangcheon_processed (admin_dong_name);

create index if not exists commercial_stores_yangcheon_category_idx
    on public.commercial_stores_yangcheon_processed (
        category_large_name,
        category_medium_name,
        category_small_name
    );

create index if not exists commercial_stores_yangcheon_lon_lat_idx
    on public.commercial_stores_yangcheon_processed (longitude, latitude);

alter table public.commercial_stores_yangcheon_processed enable row level security;
