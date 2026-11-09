-- =====================================================================================
-- Slide Studio v45 — Telegram bot jadvallari.  Supabase → SQL Editor → shu faylni to'liq ishga tushiring.
-- Faqat MA'LUMOT saqlanadi (fayllar emas): bog'lanish, qisqa slayd JSON (matn) va bir martalik kodlar.
-- RLS yoqilgan, policy yo'q: jadvallarga faqat server (service_role kaliti) kira oladi.
-- =====================================================================================

-- 1) Telegram ID  <->  sayt akkaunti (Google orqali kirgan) bog'lanishi.
create table if not exists public.tg_links (
  tg_id      bigint primary key,
  user_id    uuid   not null unique,
  email      text   not null,
  created_at timestamptz not null default now()
);

-- 2) Bir martalik ulash kodlari (10 daqiqa yashaydi)
create table if not exists public.tg_link_codes (
  code       text primary key,
  user_id    uuid not null,
  email      text not null,
  expires_at timestamptz not null
);
create index if not exists tg_link_codes_user_idx on public.tg_link_codes (user_id);

-- 3) Oxirgi slaydlar (har foydalanuvchiga eng ko'pi 5 ta; faqat qisqa JSON matn)
create table if not exists public.tg_decks (
  id         bigint generated always as identity primary key,
  tg_id      bigint not null,
  user_id    uuid,
  title      text not null default '',
  topic      text not null default '',
  lang       text not null default 'uz',
  deck       jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists tg_decks_tg_idx on public.tg_decks (tg_id, created_at desc);

alter table public.tg_links      enable row level security;
alter table public.tg_link_codes enable row level security;
alter table public.tg_decks      enable row level security;
