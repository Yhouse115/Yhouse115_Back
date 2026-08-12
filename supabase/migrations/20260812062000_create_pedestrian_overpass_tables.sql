create table if not exists public.pedestrian_overpasses_yangcheon_raw (
    source_row_number integer primary key,
    sigungu_code text,
    sigungu_name text not null default '양천구',
    emd_code text,
    emd_name text,
    node_type text,
    node_type_code text,
    node_id bigint,
    link_id bigint,
    link_type_code text,
    begin_link_id bigint,
    end_link_id bigint,
    link_length double precision,
    geometry_type text not null,
    longitude double precision,
    latitude double precision,
    node_wkt text,
    link_wkt text,
    geometry_geojson jsonb not null,
    raw_api_payload jsonb not null,
    raw_geojson_feature jsonb not null,
    source_crs text not null default 'urn:ogc:def:crs:OGC:1.3:CRS84',
    source_encoding text not null default 'utf-8',
    loaded_at timestamptz not null default now()
);

create index if not exists pedestrian_overpasses_yangcheon_raw_node_type_idx
    on public.pedestrian_overpasses_yangcheon_raw (node_type);

create index if not exists pedestrian_overpasses_yangcheon_raw_emd_idx
    on public.pedestrian_overpasses_yangcheon_raw (emd_name);

create index if not exists pedestrian_overpasses_yangcheon_raw_lon_lat_idx
    on public.pedestrian_overpasses_yangcheon_raw (longitude, latitude);

alter table public.pedestrian_overpasses_yangcheon_raw enable row level security;

create table if not exists public.pedestrian_overpasses_yangcheon_processed (
    source_row_number integer primary key,
    sigungu_name text not null default '양천구',
    emd_name text,
    node_type text not null,
    node_id bigint,
    link_id bigint,
    link_length double precision,
    geometry_type text not null,
    longitude double precision,
    latitude double precision,
    geometry_geojson jsonb not null,
    display_name text not null,
    processed_at timestamptz not null default now()
);

create index if not exists pedestrian_overpasses_yangcheon_processed_node_type_idx
    on public.pedestrian_overpasses_yangcheon_processed (node_type);

create index if not exists pedestrian_overpasses_yangcheon_processed_emd_idx
    on public.pedestrian_overpasses_yangcheon_processed (emd_name);

create index if not exists pedestrian_overpasses_yangcheon_processed_lon_lat_idx
    on public.pedestrian_overpasses_yangcheon_processed (longitude, latitude);

alter table public.pedestrian_overpasses_yangcheon_processed enable row level security;
