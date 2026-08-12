create table if not exists public.childcare_centers_seoul_raw (
    source_row_number integer primary key,
    sido_name text not null,
    sigungu_name text not null,
    center_name text not null,
    center_type text,
    operation_status text,
    postal_code text,
    address text not null,
    phone_number text,
    fax_number text,
    childcare_room_count integer,
    childcare_room_area double precision,
    playground_count integer,
    cctv_count integer,
    staff_count integer,
    capacity_count integer,
    current_child_count integer,
    latitude double precision,
    longitude double precision,
    school_bus_yn text,
    homepage_url text,
    authorized_date date,
    suspension_start_date date,
    suspension_end_date date,
    source_sheet text not null default '어린이집기본정보조회(정기)-기준일(20260731)',
    source_standard_date date not null default '2026-07-31',
    raw_payload jsonb not null,
    loaded_at timestamptz not null default now()
);

create index if not exists childcare_centers_seoul_sigungu_idx
    on public.childcare_centers_seoul_raw (sigungu_name);

create index if not exists childcare_centers_seoul_type_idx
    on public.childcare_centers_seoul_raw (center_type);

create index if not exists childcare_centers_seoul_status_idx
    on public.childcare_centers_seoul_raw (operation_status);

create index if not exists childcare_centers_seoul_lon_lat_idx
    on public.childcare_centers_seoul_raw (longitude, latitude);

alter table public.childcare_centers_seoul_raw enable row level security;

create table if not exists public.childcare_centers_yangcheon_processed (
    source_row_number integer primary key,
    sido_name text not null default '서울특별시',
    sigungu_name text not null default '양천구',
    center_name text not null,
    center_type text,
    operation_status text,
    address text not null,
    phone_number text,
    childcare_room_count integer,
    childcare_room_area double precision,
    playground_count integer,
    cctv_count integer,
    staff_count integer,
    capacity_count integer,
    current_child_count integer,
    latitude double precision not null,
    longitude double precision not null,
    school_bus_yn text,
    homepage_url text,
    authorized_date date,
    display_name text not null,
    processed_at timestamptz not null default now()
);

create index if not exists childcare_centers_yangcheon_type_idx
    on public.childcare_centers_yangcheon_processed (center_type);

create index if not exists childcare_centers_yangcheon_status_idx
    on public.childcare_centers_yangcheon_processed (operation_status);

create index if not exists childcare_centers_yangcheon_lon_lat_idx
    on public.childcare_centers_yangcheon_processed (longitude, latitude);

alter table public.childcare_centers_yangcheon_processed enable row level security;
