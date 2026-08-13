-- Keep the database axis value aligned with the public environment API.
--
-- The initial serving migration used `daily_convenience`; the API contract
-- exposes the fifth card as `convenience`. This migration is intentionally
-- additive because the initial migration has already been applied remotely.

begin;

alter table public.environment_feature
    drop constraint if exists environment_feature_axis_check;

update public.environment_feature
set axis = 'convenience'
where axis = 'daily_convenience';

alter table public.environment_feature
    add constraint environment_feature_axis_check check (axis in (
        'transport',
        'parks_play',
        'medical',
        'education_care',
        'convenience',
        'safety'
    ));

comment on column public.environment_feature.axis is
    'UI or map-layer axis: transport, parks_play, medical, education_care, convenience, or safety.';

commit;
