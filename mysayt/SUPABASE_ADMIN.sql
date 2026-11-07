-- =====================================================================
-- SUPABASE_ADMIN.sql  (v47)  —  Pro / VIP / cheksiz / reklama / admin panel
-- Supabase → SQL Editor → shu faylni BIR MARTA ishga tushiring.
-- Qayta ishga tushirsangiz ham xavfsiz (hammasi IF NOT EXISTS).
-- Mavjud jadvallar (user_usage, tg_links, ...) o'chirilmaydi.
-- =====================================================================

-- 1) Foydalanuvchi rejasi va limitlari (user_usage ga ustunlar)
alter table public.user_usage add column if not exists plan text not null default 'free';          -- free | pro | vip
alter table public.user_usage add column if not exists plan_until timestamptz;                      -- Pro tugash vaqti (NULL = muddatsiz)
alter table public.user_usage add column if not exists unlimited boolean not null default false;    -- admin "cheksiz" qilib bergan
alter table public.user_usage add column if not exists daily_units_override integer;                -- shaxsiy kunlik bepul limit (birlik; 1 Tez-varaq = 20)
alter table public.user_usage add column if not exists admin_note text;                             -- admin izohi
alter table public.user_usage add column if not exists blocked boolean not null default false;

-- 2) Reklamalar
create table if not exists public.ads (
  id            bigserial primary key,
  title         text not null default '',
  body          text not null default '',
  media_type    text not null default 'none' check (media_type in ('none','image','video')),
  media_url     text not null default '',
  link_url      text not null default '',
  button_text   text not null default 'Batafsil',
  placement     text not null default 'both' check (placement in ('both','site','bot')),
  active        boolean not null default true,
  weight        integer not null default 1,
  starts_at     timestamptz,
  ends_at       timestamptz,
  impressions   bigint not null default 0,
  clicks        bigint not null default 0,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
create index if not exists ads_active_idx on public.ads (active, placement);

-- reklama hisoblagichi (race-condition yo'q: bitta atomik UPDATE)
create or replace function public.ad_bump(p_id bigint, p_kind text)
returns void language plpgsql security definer set search_path = public as $$
begin
  if p_kind = 'click' then
    update public.ads set clicks = clicks + 1 where id = p_id;
  else
    update public.ads set impressions = impressions + 1 where id = p_id;
  end if;
end $$;

-- 3) Umumiy sozlamalar (admin paneldan o'zgartiriladi)
create table if not exists public.app_settings (
  key        text primary key,
  value      jsonb not null default 'null'::jsonb,
  updated_at timestamptz not null default now()
);

-- 4) Admin harakatlari jurnali (kim, nima qildi)
create table if not exists public.admin_audit (
  id         bigserial primary key,
  actor      text not null default '',
  action     text not null default '',
  target     text not null default '',
  details    jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists admin_audit_created_idx on public.admin_audit (created_at desc);

-- 5) Xavfsizlik: bu jadvallarga faqat server (service_role) kiradi
alter table public.ads            enable row level security;
alter table public.app_settings   enable row level security;
alter table public.admin_audit    enable row level security;
-- (policy yo'q = anon/authenticated hech narsa o'qiy olmaydi; service_role RLS'ni chetlab o'tadi)

-- 6) payment_events (agar hali yaratilmagan bo'lsa) — to'lovni ikki marta hisoblamaslik uchun
create table if not exists public.payment_events (
  order_id   text primary key,
  user_id    text,
  pages      integer,
  created_at timestamptz default now()
);
alter table public.payment_events enable row level security;

-- 7) usage_ledger (agar yo'q bo'lsa)
create table if not exists public.usage_ledger (
  id          bigserial primary key,
  user_id     text not null,
  kind        text not null default '',
  amount      integer not null default 0,
  free_after  integer not null default 0,
  paid_after  integer not null default 0,
  searches    integer not null default 0,
  details     jsonb not null default '{}'::jsonb,
  created_at  timestamptz not null default now()
);
create index if not exists usage_ledger_user_idx on public.usage_ledger (user_id, created_at desc);
alter table public.usage_ledger enable row level security;
