create table if not exists public.cctv_seoul_raw (
    management_number text primary key,
    local_government_code text,
    managing_agency_name text,
    road_address text,
    lot_address text,
    purpose_type text,
    camera_count integer,
    camera_pixel_count integer,
    filming_direction_info text,
    retention_days integer,
    installed_year_month text,
    managing_agency_phone text,
    latitude double precision,
    longitude double precision,
    data_reference_date date,
    data_update_type text,
    data_updated_at timestamp,
    last_modified_at timestamp,
    source_encoding text not null default 'cp949',
    loaded_at timestamptz not null default now()
);

create index if not exists cctv_seoul_raw_agency_idx
    on public.cctv_seoul_raw (managing_agency_name);

create index if not exists cctv_seoul_raw_purpose_idx
    on public.cctv_seoul_raw (purpose_type);

create index if not exists cctv_seoul_raw_lon_lat_idx
    on public.cctv_seoul_raw (longitude, latitude);

alter table public.cctv_seoul_raw enable row level security;

create table if not exists public.cctv_yangcheon_processed (
    management_number text primary key,
    managing_agency_name text,
    road_address text,
    lot_address text,
    purpose_type text,
    camera_count integer not null default 0,
    camera_pixel_count integer,
    filming_direction_info text,
    retention_days integer,
    installed_year_month text,
    managing_agency_phone text,
    latitude double precision not null,
    longitude double precision not null,
    sigungu_name text not null default '양천구',
    display_address text not null,
    data_reference_date date,
    processed_at timestamptz not null default now()
);

create index if not exists cctv_yangcheon_purpose_idx
    on public.cctv_yangcheon_processed (purpose_type);

create index if not exists cctv_yangcheon_lon_lat_idx
    on public.cctv_yangcheon_processed (longitude, latitude);

alter table public.cctv_yangcheon_processed enable row level security;
