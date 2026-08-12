create table if not exists public.child_safety_zones_seoul_raw (
    source_row_number integer primary key,
    sequence_number integer not null,
    sigungu_name text not null,
    administrative_dong text,
    road_address text,
    facility_name text not null,
    facility_type text,
    designated_year integer,
    full_road_address text,
    source_sheet text not null default '어린이보호구역 지정현황',
    source_standard_date date not null default '2026-06-30',
    raw_payload jsonb not null,
    loaded_at timestamptz not null default now()
);

create index if not exists child_safety_zones_seoul_sigungu_idx
    on public.child_safety_zones_seoul_raw (sigungu_name);

create index if not exists child_safety_zones_seoul_facility_type_idx
    on public.child_safety_zones_seoul_raw (facility_type);

create index if not exists child_safety_zones_seoul_facility_name_idx
    on public.child_safety_zones_seoul_raw (facility_name);

alter table public.child_safety_zones_seoul_raw enable row level security;

create table if not exists public.child_safety_zones_yangcheon_processed (
    source_row_number integer primary key,
    sequence_number integer not null,
    sigungu_name text not null default '양천구',
    administrative_dong text,
    road_address text,
    facility_name text not null,
    facility_type text,
    designated_year integer,
    full_road_address text not null,
    display_name text not null,
    source_standard_date date not null default '2026-06-30',
    processed_at timestamptz not null default now()
);

create index if not exists child_safety_zones_yangcheon_facility_type_idx
    on public.child_safety_zones_yangcheon_processed (facility_type);

create index if not exists child_safety_zones_yangcheon_facility_name_idx
    on public.child_safety_zones_yangcheon_processed (facility_name);

alter table public.child_safety_zones_yangcheon_processed enable row level security;
