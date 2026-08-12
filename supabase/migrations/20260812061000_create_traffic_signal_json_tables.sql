create table if not exists public.traffic_signals_json_seoul_raw (
    management_number text primary key,
    sequence_number integer,
    road_office_name text,
    sigungu_name text,
    intersection_name text,
    installed_date date,
    replaced_date date,
    x_coord double precision,
    y_coord double precision,
    address text,
    intersection_type text,
    signal_color_type text,
    raw_payload jsonb not null,
    source_format text not null default 'json',
    source_encoding text not null default 'utf-8',
    loaded_at timestamptz not null default now()
);

create index if not exists traffic_signals_json_seoul_sigungu_idx
    on public.traffic_signals_json_seoul_raw (sigungu_name);

create index if not exists traffic_signals_json_seoul_xy_idx
    on public.traffic_signals_json_seoul_raw (x_coord, y_coord);

alter table public.traffic_signals_json_seoul_raw enable row level security;

create table if not exists public.traffic_signals_json_yangcheon_processed (
    management_number text primary key,
    sequence_number integer,
    road_office_name text,
    sigungu_name text not null default '양천구',
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

create index if not exists traffic_signals_json_yangcheon_xy_idx
    on public.traffic_signals_json_yangcheon_processed (x_coord, y_coord);

alter table public.traffic_signals_json_yangcheon_processed enable row level security;
