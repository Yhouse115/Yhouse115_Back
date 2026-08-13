-- Serving tables for the apartment environment API.
--
-- Raw source-specific tables remain ingestion inputs. These tables contain the
-- normalized feature and pre-computed walking results used by the API so the
-- request path never recalculates distances from coordinates. `environment_feature`
-- serves the five UI axes and the safety layer together.

begin;

create extension if not exists postgis;

create table if not exists public.source_dataset (
    source_dataset_id text primary key,
    source_name text not null,
    source_file text,
    source_sha256 text,
    reference_date text,
    license_name text,
    metadata jsonb not null default '{}'::jsonb,
    loaded_at timestamptz not null default now()
);

create table if not exists public.environment_feature (
    feature_id text primary key,
    source_dataset_id text not null references public.source_dataset (source_dataset_id),
    source_record_id text not null,
    layer_category text not null,
    axis text not null check (axis in (
        'transport',
        'parks_play',
        'medical',
        'education_care',
        'daily_convenience',
        'safety'
    )),
    feature_type text not null,
    parent_feature_id text references public.environment_feature (feature_id)
        deferrable initially deferred,
    line_names text[] not null default '{}'::text[],
    service_types text[] not null default '{}'::text[],
    name text,
    address text,
    scope_role text not null default 'yangcheon' check (
        scope_role in ('yangcheon', 'boundary_support')
    ),
    longitude numeric(10, 7) not null check (longitude between 124 and 132),
    latitude numeric(9, 7) not null check (latitude between 33 and 39),
    location geography(point, 4326) generated always as (
        st_setsrid(st_makepoint(longitude, latitude), 4326)::geography
    ) stored,
    geometry geometry(geometry, 4326),
    coordinate_status text not null,
    coordinate_method text not null,
    record_status text not null default 'unknown',
    map_visible boolean not null default true,
    reference_date text,
    attributes jsonb not null default '{}'::jsonb,
    qa_flags text[] not null default '{}'::text[],
    loaded_at timestamptz not null default now(),
    constraint environment_feature_source_record_key unique (source_dataset_id, source_record_id)
);

create index if not exists environment_feature_location_gix
    on public.environment_feature using gist (location);

create index if not exists environment_feature_category_type_idx
    on public.environment_feature (axis, feature_type, record_status);

create index if not exists environment_feature_parent_feature_idx
    on public.environment_feature (parent_feature_id)
    where parent_feature_id is not null;

create index if not exists environment_feature_visible_axis_idx
    on public.environment_feature (axis, feature_type)
    where map_visible;

create index if not exists environment_feature_service_types_gin
    on public.environment_feature using gin (service_types);

create index if not exists environment_feature_line_names_gin
    on public.environment_feature using gin (line_names);

comment on table public.environment_feature is
    'Normalized map-serving facilities for transport, parks/play, medical, education/care, daily convenience, and safety. Raw source tables remain the ingestion record.';
comment on column public.environment_feature.axis is
    'UI axis: transport, parks_play, medical, education_care, daily_convenience, or safety.';
comment on column public.environment_feature.parent_feature_id is
    'Parent facility relationship, for example a subway exit pointing to its physical station.';
comment on column public.environment_feature.scope_role is
    'yangcheon for the primary product area; boundary_support only for an external facility needed to explain a nearest-access result.';

create table if not exists public.complex_feature_access (
    -- Existing public.apartment_complex is the map-serving apartment master.
    -- Its CX-* complex_id is retained end-to-end in walking outputs and API
    -- responses. KREB tables remain raw/reference inputs, not this key.
    complex_id text not null,
    feature_id text not null references public.environment_feature (feature_id),
    access_group text not null,
    main_origin_id text not null,
    origin_method text not null,
    calculation_version text not null,
    policy_version text,
    reference_date text,
    straight_distance_m double precision check (straight_distance_m is null or straight_distance_m >= 0),
    walk_distance_m double precision check (walk_distance_m is null or walk_distance_m >= 0),
    walk_time_min double precision check (walk_time_min is null or walk_time_min >= 0),
    distance_method text not null,
    access_status text not null,
    category_distance_limit_m double precision check (category_distance_limit_m is null or category_distance_limit_m >= 0),
    is_nearest boolean not null default false,
    selection_reason text,
    failure_reason text,
    qa_flags text[] not null default '{}'::text[],
    loaded_at timestamptz not null default now(),
    primary key (complex_id, feature_id, access_group, main_origin_id, calculation_version)
);

create index if not exists complex_feature_access_group_idx
    on public.complex_feature_access (complex_id, access_group, walk_time_min, walk_distance_m);

create index if not exists complex_feature_access_feature_idx
    on public.complex_feature_access (feature_id);

create table if not exists public.complex_environment_summary (
    complex_id text not null,
    access_group text not null,
    main_origin_id text not null,
    origin_method text not null,
    calculation_version text not null,
    policy_version text,
    reference_date text,
    category_distance_limit_m double precision check (category_distance_limit_m is null or category_distance_limit_m >= 0),
    nearest_feature_id text references public.environment_feature (feature_id),
    nearest_walk_distance_m double precision check (nearest_walk_distance_m is null or nearest_walk_distance_m >= 0),
    nearest_walk_time_min double precision check (nearest_walk_time_min is null or nearest_walk_time_min >= 0),
    count_within_5min integer not null default 0 check (count_within_5min >= 0),
    count_within_10min integer not null default 0 check (count_within_10min >= 0),
    count_within_15min integer not null default 0 check (count_within_15min >= 0),
    selected_feature_count integer not null default 0 check (selected_feature_count >= 0),
    metrics jsonb not null default '{}'::jsonb,
    summary_status text not null,
    failure_reason text,
    qa_flags text[] not null default '{}'::text[],
    loaded_at timestamptz not null default now(),
    primary key (complex_id, access_group, calculation_version)
);

create index if not exists complex_environment_summary_group_idx
    on public.complex_environment_summary (complex_id, access_group, summary_status);

do $$
begin
    if exists (select 1 from pg_roles where rolname = 'service_role') then
        grant select, insert, update, delete on public.source_dataset to service_role;
        grant select, insert, update, delete on public.environment_feature to service_role;
        grant select, insert, update, delete on public.complex_feature_access to service_role;
        grant select, insert, update, delete on public.complex_environment_summary to service_role;
    end if;
end
$$;

commit;
