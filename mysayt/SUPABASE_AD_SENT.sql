-- =====================================================================================
-- Slide Studio v51 — botga yuborilgan reklama xabarlari ro'yxati.
-- Supabase -> SQL Editor -> shu faylni BIR MARTA ishga tushiring.
-- Nima uchun kerak: reklama o'chirilganda uning xabarlari foydalanuvchilar chatidan ham o'chishi uchun
-- (oldin ro'yxat serverning vaqtinchalik xotirasida edi — server qayta ishga tushsa yo'qolib, xabarlar chatda qolib ketardi).
-- RLS yoqilgan, policy yo'q: faqat server (service_role) kira oladi.
-- =====================================================================================
create table if not exists public.ad_sent (
  id       bigint generated always as identity primary key,
  ad_id    bigint      not null,
  chat_id  bigint      not null,
  msg_id   bigint      not null,
  sent_at  timestamptz not null default now()
);
create index if not exists ad_sent_ad_idx   on public.ad_sent (ad_id);
create index if not exists ad_sent_time_idx on public.ad_sent (sent_at);
alter table public.ad_sent enable row level security;
