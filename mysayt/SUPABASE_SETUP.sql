-- ============================================================================
-- Slide Studio v38 — TO'LIQ Supabase sozlash (noldan). Qayta ishga tushirish xavfsiz.
-- Balans BIRLIKDA: 1 Tez-varaq = 20 birlik, 1 Chuqur-varaq = 60 birlik
--   bepul kuniga 300 birlik = 15 Tez-varaq = 5 Chuqur-varaq
--   $1 = 3000 birlik       = 150 Tez-varaq = 50 Chuqur-varaq
-- Bazada FAQAT: akkauntlar (Auth), balans, to'lovlar, referal, fikrlar. Slaydlar saqlanmaydi.
-- ============================================================================

-- 0) "Database error saving new user" sababi: auth.users dagi eski triggerlarni olib tashlaymiz
do $$
declare r record;
begin
  for r in select tgname from pg_trigger
            where tgrelid = 'auth.users'::regclass and not tgisinternal loop
    execute format('drop trigger if exists %I on auth.users', r.tgname);
  end loop;
end $$;
drop function if exists public.handle_new_user() cascade;
drop function if exists public.create_user_usage() cascade;

-- 1) Foydalanuvchi balansi va statistikasi
create table if not exists public.user_usage (
  user_id          text primary key,
  email            text,
  free_credits     int          not null default 300,
  paid_credits     int          not null default 0,
  slide_credits    int          not null default 300,
  prompt_count     int          not null default 0,
  search_count     int          not null default 0,
  last_reset_time  timestamptz  not null default now(),
  total_tokens     bigint       not null default 0,
  daily_tokens     bigint       not null default 0,
  daily_reset      timestamptz,
  blocked          boolean      not null default false,
  last_active      timestamptz,
  created_at       timestamptz  not null default now()
);
create index if not exists user_usage_email_idx on public.user_usage (email);

alter table public.user_usage add column if not exists email text;
alter table public.user_usage add column if not exists free_credits int not null default 300;
alter table public.user_usage add column if not exists paid_credits int not null default 0;
alter table public.user_usage add column if not exists slide_credits int not null default 300;
alter table public.user_usage add column if not exists prompt_count int not null default 0;
alter table public.user_usage add column if not exists search_count int not null default 0;
alter table public.user_usage add column if not exists last_reset_time timestamptz not null default now();
alter table public.user_usage add column if not exists total_tokens bigint not null default 0;
alter table public.user_usage add column if not exists daily_tokens bigint not null default 0;
alter table public.user_usage add column if not exists daily_reset timestamptz;
alter table public.user_usage add column if not exists blocked boolean not null default false;
alter table public.user_usage add column if not exists last_active timestamptz;

-- 2) Balans jurnali (BIRLIKda)
create table if not exists public.usage_ledger (
  id          bigint generated always as identity primary key,
  user_id     text        not null,
  created_at  timestamptz not null default now(),
  kind        text        not null,
  amount      int         not null,
  free_after  int,
  paid_after  int,
  searches    int         not null default 0,
  details     jsonb       not null default '{}'::jsonb
);
create index if not exists usage_ledger_user_time_idx on public.usage_ledger (user_id, created_at desc);

-- 3) To'lovlar (webhook takrorlanmasligi uchun)
create table if not exists public.payment_events (
  order_id    text primary key,
  user_id     text,
  pages       int,
  created_at  timestamptz default now()
);

-- 4) Referal
create table if not exists public.referral_codes (
  user_id text primary key,
  code    text unique not null
);
create table if not exists public.referrals (
  invitee_id text primary key,
  inviter_id text not null,
  code       text,
  pages      int default 15,
  created_at timestamptz default now()
);
create index if not exists referrals_inviter_idx on public.referrals (inviter_id);

-- 5) Fikrlar (izohlar + layklar)
create table if not exists public.feedback_posts (
  id         uuid primary key,
  user_id    text not null,
  author     text,
  body       text not null,
  parent_id  uuid references public.feedback_posts(id) on delete cascade,
  created_at timestamptz default now()
);
create table if not exists public.feedback_likes (
  post_id uuid not null references public.feedback_posts(id) on delete cascade,
  user_id text not null,
  primary key (post_id, user_id)
);
create index if not exists idx_feedback_posts_created on public.feedback_posts (created_at desc);
create index if not exists idx_feedback_posts_parent  on public.feedback_posts (parent_id);
create index if not exists idx_feedback_likes_post    on public.feedback_likes (post_id);

-- 6) Xavfsizlik (RLS): brauzer jadvallarga to'g'ridan-to'g'ri kirmaydi; hammasi serverdagi service_role orqali
alter table public.user_usage      enable row level security;
alter table public.usage_ledger    enable row level security;
alter table public.payment_events  enable row level security;
alter table public.referral_codes  enable row level security;
alter table public.referrals       enable row level security;
alter table public.feedback_posts  enable row level security;
alter table public.feedback_likes  enable row level security;

drop policy if exists "public_read_posts"  on public.feedback_posts;
drop policy if exists "public_read_likes"  on public.feedback_likes;
drop policy if exists "allow_insert_posts" on public.feedback_posts;
drop policy if exists "allow_delete_posts" on public.feedback_posts;
drop policy if exists "allow_insert_likes" on public.feedback_likes;
drop policy if exists "allow_delete_likes" on public.feedback_likes;

-- 7) Eski taqdimotlar jadvali endi kerak emas
drop table if exists public.presentations;