-- Pre-computed route geometries for map rendering.
--
-- `complex_feature_access` remains the compact access-facts table. This table
-- stores only the selected route geometry so a map request can render a route
-- without recalculating a shortest path from the walking network.

begin;

create table if not exists public.complex_feature_walking_route (
    complex_id text not null references public.apartment_complex (complex_id),
    feature_id text not null references public.environment_feature (feature_id),
    access_group text not null,
    main_origin_id text not null,
    calculation_version text not null,
    route_coordinates jsonb not null,
    walk_distance_m double precision not null check (walk_distance_m >= 0),
    walk_time_min double precision not null check (walk_time_min >= 0),
    route_method text not null,
    calculated_at timestamptz not null,
    route_metadata jsonb not null default '{}'::jsonb,
    qa_flags text[] not null default '{}'::text[],
    loaded_at timestamptz not null default now(),
    primary key (complex_id, feature_id, access_group, main_origin_id, calculation_version),
    constraint complex_feature_walking_route_coordinates_check check (
        jsonb_typeof(route_coordinates) = 'array'
        and jsonb_array_length(route_coordinates) >= 2
    )
);

create index if not exists complex_feature_walking_route_lookup_idx
    on public.complex_feature_walking_route (
        complex_id,
        feature_id,
        access_group,
        main_origin_id,
        calculated_at desc,
        calculation_version desc
    );

alter table public.complex_feature_walking_route enable row level security;

comment on table public.complex_feature_walking_route is
    'Pre-computed map route coordinates. API requests read one stored row and never execute shortest-path routing.';
comment on column public.complex_feature_walking_route.route_coordinates is
    'GeoJSON-position order: [longitude, latitude].';
comment on column public.complex_feature_walking_route.route_metadata is
    'Non-contract diagnostics such as graph and snap-leg distances from the local route export.';

do $$
begin
    if exists (select 1 from pg_roles where rolname = 'service_role') then
        grant select, insert, update, delete on public.complex_feature_walking_route to service_role;
    end if;
end
$$;

commit;
