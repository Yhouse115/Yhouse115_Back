create table if not exists public.crosswalk_locations_seoul_raw (
    source_row_number integer primary key,
    node_link_type text not null,
    node_wkt text,
    node_id bigint,
    node_type_code text,
    link_wkt text,
    link_id bigint,
    link_type_code text,
    begin_node_id bigint,
    end_node_id bigint,
    link_length double precision,
    sigungu_code text not null,
    sigungu_name text not null,
    emd_code text,
    emd_name text,
    geometry_type text not null,
    longitude double precision not null,
    latitude double precision not null,
    geometry_geojson jsonb not null,
    source_encoding text not null default 'cp949',
    raw_payload jsonb not null,
    loaded_at timestamptz not null default now()
);

create unique index if not exists crosswalk_locations_seoul_node_link_unique_idx
    on public.crosswalk_locations_seoul_raw (node_link_type, node_id, link_id);

create index if not exists crosswalk_locations_seoul_sigungu_idx
    on public.crosswalk_locations_seoul_raw (sigungu_name);

create index if not exists crosswalk_locations_seoul_emd_idx
    on public.crosswalk_locations_seoul_raw (emd_name);

create index if not exists crosswalk_locations_seoul_lon_lat_idx
    on public.crosswalk_locations_seoul_raw (longitude, latitude);

alter table public.crosswalk_locations_seoul_raw enable row level security;

create table if not exists public.crosswalk_locations_yangcheon_processed (
    source_row_number integer primary key,
    node_link_type text not null,
    sigungu_code text not null default '1147000000',
    sigungu_name text not null default '양천구',
    emd_code text,
    emd_name text,
    node_id bigint,
    link_id bigint,
    link_length double precision,
    geometry_type text not null,
    longitude double precision not null,
    latitude double precision not null,
    geometry_geojson jsonb not null,
    display_name text not null,
    processed_at timestamptz not null default now()
);

create index if not exists crosswalk_locations_yangcheon_type_idx
    on public.crosswalk_locations_yangcheon_processed (node_link_type);

create index if not exists crosswalk_locations_yangcheon_emd_idx
    on public.crosswalk_locations_yangcheon_processed (emd_name);

create index if not exists crosswalk_locations_yangcheon_lon_lat_idx
    on public.crosswalk_locations_yangcheon_processed (longitude, latitude);

alter table public.crosswalk_locations_yangcheon_processed enable row level security;
