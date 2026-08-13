-- 앱 전용 프로필 (auth.users를 확장)
create table user_profiles (
  user_id     uuid primary key references auth.users(id) on delete cascade,
  nickname    text,
  avatar_url  text,
  created_at  timestamptz not null default now()
);

alter table user_profiles enable row level security;

create policy "본인 프로필만 조회"
  on user_profiles for select
  using (auth.uid() = user_id);

create policy "본인 프로필만 수정"
  on user_profiles for update
  using (auth.uid() = user_id);

-- 가입 시 Google 프로필(raw_user_meta_data)에서 이름/사진을 끌어와 자동 생성
create function handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.user_profiles (user_id, nickname, avatar_url)
  values (
    new.id,
    coalesce(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name'),
    new.raw_user_meta_data->>'avatar_url'
  );
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function handle_new_user();
