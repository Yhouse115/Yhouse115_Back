-- Exact crossing events selected from the OA-21208 links traversed by each
-- stored walking route. This replaces the old "near the route" interpretation
-- for crosswalk and pedestrian-signal counts.

begin;

alter table public.complex_feature_walking_route
    add column if not exists route_crossing_events jsonb;

alter table public.complex_feature_walking_route
    drop constraint if exists complex_feature_walking_route_crossing_events_check,
    add constraint complex_feature_walking_route_crossing_events_check
        check (
            route_crossing_events is null
            or jsonb_typeof(route_crossing_events) = 'array'
        );

comment on column public.complex_feature_walking_route.route_crossing_events is
    'One clustered crosswalk-node event exactly present on the stored route; includes marker coordinates and attached pedestrian-signal coordinates.';
comment on column public.complex_feature_walking_route.crosswalk_count is
    'Count of clustered crosswalk-source nodes exactly present on the stored walking route when route_crossing_events is present.';
comment on column public.complex_feature_walking_route.pedestrian_signal_count is
    'Distinct pedestrian-signal locations within the matching threshold of an exact route-crosswalk event when route_crossing_events is present.';

commit;
