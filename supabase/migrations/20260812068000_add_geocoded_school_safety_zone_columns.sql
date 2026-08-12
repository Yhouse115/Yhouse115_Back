alter table public.elementary_schools_yangcheon_processed
    add column if not exists longitude double precision,
    add column if not exists latitude double precision;

create index if not exists elementary_schools_yangcheon_lon_lat_idx
    on public.elementary_schools_yangcheon_processed (longitude, latitude);

alter table public.child_safety_zones_yangcheon_processed
    add column if not exists longitude double precision,
    add column if not exists latitude double precision;

create index if not exists child_safety_zones_yangcheon_lon_lat_idx
    on public.child_safety_zones_yangcheon_processed (longitude, latitude);
