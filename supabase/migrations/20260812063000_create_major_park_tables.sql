create table if not exists public.major_parks_seoul_raw (
    source_row_number integer primary key,
    sequence_number integer not null,
    managing_department text,
    phone_number text,
    park_name text not null,
    park_overview text,
    area_text text,
    area_square_meters double precision,
    opened_date_text text,
    main_facilities text,
    main_plants text,
    guide_map_url text,
    directions text,
    usage_notes text,
    image_url text,
    sigungu_name text,
    address text not null,
    grs80tm_x double precision,
    grs80tm_y double precision,
    longitude double precision,
    latitude double precision,
    detail_url text,
    source_sheet text not null default '서울시 주요 공원현황',
    source_standard_period text not null default '2026 상반기',
    raw_payload jsonb not null,
    loaded_at timestamptz not null default now()
);

create index if not exists major_parks_seoul_sigungu_idx
    on public.major_parks_seoul_raw (sigungu_name);

create index if not exists major_parks_seoul_park_name_idx
    on public.major_parks_seoul_raw (park_name);

create index if not exists major_parks_seoul_lon_lat_idx
    on public.major_parks_seoul_raw (longitude, latitude);

alter table public.major_parks_seoul_raw enable row level security;

create table if not exists public.major_parks_yangcheon_processed (
    source_row_number integer primary key,
    sequence_number integer not null,
    sigungu_name text not null default '양천구',
    park_name text not null,
    managing_department text,
    phone_number text,
    address text not null,
    area_text text,
    area_square_meters double precision,
    opened_date_text text,
    main_facilities text,
    main_plants text,
    guide_map_url text,
    image_url text,
    detail_url text,
    longitude double precision not null,
    latitude double precision not null,
    display_name text not null,
    processed_at timestamptz not null default now()
);

create index if not exists major_parks_yangcheon_park_name_idx
    on public.major_parks_yangcheon_processed (park_name);

create index if not exists major_parks_yangcheon_lon_lat_idx
    on public.major_parks_yangcheon_processed (longitude, latitude);

alter table public.major_parks_yangcheon_processed enable row level security;
