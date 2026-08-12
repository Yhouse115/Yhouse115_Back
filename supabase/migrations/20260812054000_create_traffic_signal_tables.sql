create table if not exists public.traffic_signals_seoul_raw (
    sequence_number integer primary key,
    road_office_name text,
    sigungu_name text,
    device_management_number text,
    intersection_name text,
    installed_date date,
    replaced_date date,
    x_coord double precision,
    y_coord double precision,
    address text,
    intersection_type text,
    signal_color_type text,
    source_encoding text not null default 'cp949',
    loaded_at timestamptz not null default now()
);

create unique index if not exists traffic_signals_seoul_device_number_idx
    on public.traffic_signals_seoul_raw (device_management_number);

create index if not exists traffic_signals_seoul_sigungu_idx
    on public.traffic_signals_seoul_raw (sigungu_name);

create index if not exists traffic_signals_seoul_xy_idx
    on public.traffic_signals_seoul_raw (x_coord, y_coord);

alter table public.traffic_signals_seoul_raw enable row level security;

create table if not exists public.traffic_signals_yangcheon_processed (
    sequence_number integer primary key,
    road_office_name text,
    sigungu_name text not null default '양천구',
    device_management_number text,
    intersection_name text,
    installed_date date,
    replaced_date date,
    x_coord double precision not null,
    y_coord double precision not null,
    address text,
    intersection_type text,
    signal_color_type text,
    display_name text not null,
    processed_at timestamptz not null default now()
);

create unique index if not exists traffic_signals_yangcheon_device_number_idx
    on public.traffic_signals_yangcheon_processed (device_management_number);

create index if not exists traffic_signals_yangcheon_xy_idx
    on public.traffic_signals_yangcheon_processed (x_coord, y_coord);

alter table public.traffic_signals_yangcheon_processed enable row level security;
