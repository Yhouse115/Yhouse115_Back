create table if not exists public.playground_facilities_seoul_raw (
    facility_code text primary key,
    installed_date date,
    city_code text not null,
    sigungu_code text not null,
    emd_code text,
    facility_admin_code text,
    facility_legal_dong_code text,
    facility_type_code text,
    facility_category_code text,
    facility_operation_code text,
    facility_owner_code text,
    facility_status_code text,
    object_id bigint,
    facility_name text not null,
    deleted_yn text,
    accepted_yn text,
    web_mercator_x double precision not null,
    web_mercator_y double precision not null,
    longitude double precision not null,
    latitude double precision not null,
    address text,
    source_encoding text not null default 'utf-8-sig',
    raw_payload jsonb not null,
    loaded_at timestamptz not null default now()
);

create index if not exists playground_facilities_seoul_sigungu_idx
    on public.playground_facilities_seoul_raw (sigungu_code);

create index if not exists playground_facilities_seoul_facility_type_idx
    on public.playground_facilities_seoul_raw (facility_type_code);

create index if not exists playground_facilities_seoul_lon_lat_idx
    on public.playground_facilities_seoul_raw (longitude, latitude);

alter table public.playground_facilities_seoul_raw enable row level security;

create table if not exists public.playground_facilities_yangcheon_processed (
    facility_code text primary key,
    installed_date date,
    sigungu_code text not null default '11470',
    sigungu_name text not null default '양천구',
    emd_code text,
    facility_type_code text,
    facility_category_code text,
    facility_operation_code text,
    facility_owner_code text,
    facility_name text not null,
    address text,
    web_mercator_x double precision not null,
    web_mercator_y double precision not null,
    longitude double precision not null,
    latitude double precision not null,
    display_name text not null,
    processed_at timestamptz not null default now()
);

create index if not exists playground_facilities_yangcheon_facility_type_idx
    on public.playground_facilities_yangcheon_processed (facility_type_code);

create index if not exists playground_facilities_yangcheon_lon_lat_idx
    on public.playground_facilities_yangcheon_processed (longitude, latitude);

alter table public.playground_facilities_yangcheon_processed enable row level security;
