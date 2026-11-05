-- Admin / PRO ustunlari (ixtiyoriy, kod ustunsiz ham ishlaydi — paid_credits orqali)
alter table public.user_usage add column if not exists is_pro boolean not null default false;
alter table public.user_usage add column if not exists unlimited boolean not null default false;

-- Reklama sozlamalari (ixtiyoriy, asosiy .env)
create table if not exists public.admin_settings (
  key text primary key,
  value jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);
