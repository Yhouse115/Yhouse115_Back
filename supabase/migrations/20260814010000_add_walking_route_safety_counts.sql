-- Compact safety counts pre-computed against each stored walking route.
-- Individual safety-point geometries remain in their source tables and are
-- not duplicated for every route.

begin;

alter table public.complex_feature_walking_route
    add column if not exists safety_match_threshold_m smallint,
    add column if not exists crosswalk_count integer,
    add column if not exists pedestrian_signal_count integer,
    add column if not exists cctv_location_count integer,
    add column if not exists safety_calculation_version text,
    add column if not exists safety_calculated_at timestamptz;

alter table public.complex_feature_walking_route
    drop constraint if exists complex_feature_walking_route_safety_threshold_check,
    add constraint complex_feature_walking_route_safety_threshold_check
        check (safety_match_threshold_m is null or safety_match_threshold_m > 0),
    drop constraint if exists complex_feature_walking_route_crosswalk_count_check,
    add constraint complex_feature_walking_route_crosswalk_count_check
        check (crosswalk_count is null or crosswalk_count >= 0),
    drop constraint if exists complex_feature_walking_route_pedestrian_signal_count_check,
    add constraint complex_feature_walking_route_pedestrian_signal_count_check
        check (pedestrian_signal_count is null or pedestrian_signal_count >= 0),
    drop constraint if exists complex_feature_walking_route_cctv_location_count_check,
    add constraint complex_feature_walking_route_cctv_location_count_check
        check (cctv_location_count is null or cctv_location_count >= 0);

comment on column public.complex_feature_walking_route.safety_match_threshold_m is
    'Maximum point-to-route-line distance used for pre-computed safety counts, in metres.';
comment on column public.complex_feature_walking_route.crosswalk_count is
    'Distinct visual crosswalk locations within safety_match_threshold_m of the stored walking route.';
comment on column public.complex_feature_walking_route.pedestrian_signal_count is
    'Distinct pedestrian-signal locations within safety_match_threshold_m of the stored walking route.';
comment on column public.complex_feature_walking_route.cctv_location_count is
    'Distinct CCTV installation locations within safety_match_threshold_m of the stored walking route; not camera-lens total.';

commit;
