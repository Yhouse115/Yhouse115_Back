-- Link environment-serving rows to the existing CX-* apartment master.
--
-- `public.apartment_complex` is created by the apartment-serving schema and
-- is intentionally not recreated here. This migration makes that dependency
-- explicit for the environment-serving tables.

begin;

do $$
begin
    if to_regclass('public.apartment_complex') is null then
        raise exception
            'public.apartment_complex must exist before applying environment serving migrations';
    end if;

    if not exists (
        select 1
        from pg_constraint
        where conrelid = 'public.complex_feature_access'::regclass
          and conname = 'complex_feature_access_complex_id_fkey'
    ) then
        alter table public.complex_feature_access
            add constraint complex_feature_access_complex_id_fkey
            foreign key (complex_id)
            references public.apartment_complex (complex_id);
    end if;

    if not exists (
        select 1
        from pg_constraint
        where conrelid = 'public.complex_environment_summary'::regclass
          and conname = 'complex_environment_summary_complex_id_fkey'
    ) then
        alter table public.complex_environment_summary
            add constraint complex_environment_summary_complex_id_fkey
            foreign key (complex_id)
            references public.apartment_complex (complex_id);
    end if;
end
$$;

comment on column public.complex_feature_access.complex_id is
    'CX-* ID from public.apartment_complex, the map-serving apartment master.';
comment on column public.complex_environment_summary.complex_id is
    'CX-* ID from public.apartment_complex, the map-serving apartment master.';

commit;
