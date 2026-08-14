-- The product serves Yangcheon only. Keep the geocoded Yangcheon KREB
-- reference table, but do not retain the nationwide raw import in Postgres.
--
-- Deliberately omit CASCADE: any future dependency on this raw table must be
-- made explicit rather than being removed silently.
begin;

drop table if exists public.kreb_apt_complex_basic_20250918;

commit;
