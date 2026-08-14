-- 유저당 메모 1개 (아파트 비교 화면의 "비교 분석 메모")
create table user_memos (
  user_id     uuid primary key references auth.users(id) on delete cascade,
  content     text not null default '',
  updated_at  timestamptz not null default now()
);

alter table user_memos enable row level security;

create policy "본인 메모만 조회"
  on user_memos for select
  using (auth.uid() = user_id);

create policy "본인 메모만 생성"
  on user_memos for insert
  with check (auth.uid() = user_id);

create policy "본인 메모만 수정"
  on user_memos for update
  using (auth.uid() = user_id);
