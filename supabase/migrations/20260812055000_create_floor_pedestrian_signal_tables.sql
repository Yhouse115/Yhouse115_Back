create table if not exists public.floor_pedestrian_signals_seoul_raw (
    source_row_number integer primary key,
    management_number text not null,
    status_code text,
    event_code text,
    established_date date,
    changed_date date,
    maker_company text,
    work_code text,
    view_code text,
    crosswalk_management_number text,
    history_id text,
    xce double precision,
    yce double precision,
    form_code text,
    css_code text,
    old_pedestrian_signal_code text,
    gu_code text not null,
    control_yn_code text,
    dong_code text,
    jibun text,
    new_pedestrian_signal_code text,
    road_division_code text,
    traffic_basis_code text,
    managing_agency text,
    shape_type text,
    geom_x double precision,
    geom_y double precision,
    bbox_min_x double precision,
    bbox_min_y double precision,
    bbox_max_x double precision,
    bbox_max_y double precision,
    point_count integer,
    estimated_longitude double precision,
    estimated_latitude double precision,
    raw_payload jsonb not null,
    source_encoding text not null default 'utf-8-sig',
    loaded_at timestamptz not null default now()
);

create index if not exists floor_pedestrian_signals_seoul_management_number_idx
    on public.floor_pedestrian_signals_seoul_raw (management_number);

create index if not exists floor_pedestrian_signals_seoul_gu_code_idx
    on public.floor_pedestrian_signals_seoul_raw (gu_code);

create index if not exists floor_pedestrian_signals_seoul_lon_lat_idx
    on public.floor_pedestrian_signals_seoul_raw (estimated_longitude, estimated_latitude);

alter table public.floor_pedestrian_signals_seoul_raw enable row level security;

create table if not exists public.floor_pedestrian_signals_yangcheon_processed (
    source_row_number integer primary key,
    management_number text not null,
    status_code text,
    event_code text,
    established_date date,
    changed_date date,
    maker_company text,
    work_code text,
    view_code text,
    crosswalk_management_number text,
    history_id text,
    gu_code text not null default '470',
    sigungu_name text not null default '양천구',
    dong_code text,
    old_pedestrian_signal_code text,
    new_pedestrian_signal_code text,
    road_division_code text,
    traffic_basis_code text,
    geom_x double precision,
    geom_y double precision,
    estimated_longitude double precision not null,
    estimated_latitude double precision not null,
    display_name text not null,
    processed_at timestamptz not null default now()
);

create index if not exists floor_pedestrian_signals_yangcheon_management_number_idx
    on public.floor_pedestrian_signals_yangcheon_processed (management_number);

create index if not exists floor_pedestrian_signals_yangcheon_lon_lat_idx
    on public.floor_pedestrian_signals_yangcheon_processed (estimated_longitude, estimated_latitude);

alter table public.floor_pedestrian_signals_yangcheon_processed enable row level security;
