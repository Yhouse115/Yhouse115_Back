create table if not exists public.elementary_schools_seoul_raw (
    school_code text primary key,
    education_office_name text not null,
    school_name text not null,
    english_school_name text,
    school_level text not null,
    sido_name text not null,
    district_education_office_name text,
    establishment_type text,
    postal_code text,
    road_address text not null,
    detail_address text,
    phone_number text,
    homepage_url text,
    coeducation_type text,
    established_date date,
    anniversary_date date,
    source_encoding text not null default 'utf-8-sig',
    raw_payload jsonb not null,
    loaded_at timestamptz not null default now()
);

create index if not exists elementary_schools_seoul_school_name_idx
    on public.elementary_schools_seoul_raw (school_name);

create index if not exists elementary_schools_seoul_establishment_type_idx
    on public.elementary_schools_seoul_raw (establishment_type);

create index if not exists elementary_schools_seoul_district_office_idx
    on public.elementary_schools_seoul_raw (district_education_office_name);

alter table public.elementary_schools_seoul_raw enable row level security;

create table if not exists public.elementary_schools_yangcheon_processed (
    school_code text primary key,
    sigungu_name text not null default '양천구',
    education_office_name text not null,
    district_education_office_name text,
    school_name text not null,
    english_school_name text,
    school_level text not null default '초등학교',
    establishment_type text,
    postal_code text,
    road_address text not null,
    detail_address text,
    phone_number text,
    homepage_url text,
    coeducation_type text,
    established_date date,
    anniversary_date date,
    display_name text not null,
    processed_at timestamptz not null default now()
);

create index if not exists elementary_schools_yangcheon_school_name_idx
    on public.elementary_schools_yangcheon_processed (school_name);

create index if not exists elementary_schools_yangcheon_establishment_type_idx
    on public.elementary_schools_yangcheon_processed (establishment_type);

alter table public.elementary_schools_yangcheon_processed enable row level security;
