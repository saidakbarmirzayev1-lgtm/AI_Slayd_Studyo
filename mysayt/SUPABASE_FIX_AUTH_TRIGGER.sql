-- "Database error saving new user" xatosi: auth.users jadvalida ESKI loyihadan qolgan trigger bor
-- (u o'chirilgan jadvalga yozishga urinadi). Supabase → SQL Editor da ishga tushiring.

-- 1) Qaysi triggerlar bor — ko'rish uchun:
select t.tgname as trigger, p.proname as funksiya
  from pg_trigger t join pg_proc p on p.oid = t.tgfoid
 where t.tgrelid = 'auth.users'::regclass and not t.tgisinternal;

-- 2) Hammasini o'chirish (bizning ilovaga hech qanday trigger kerak emas — balans qatorini backend o'zi yaratadi):
do $$
declare r record;
begin
  for r in select tgname from pg_trigger where tgrelid = 'auth.users'::regclass and not tgisinternal loop
    execute format('drop trigger if exists %I on auth.users', r.tgname);
  end loop;
end $$;

-- 3) Odatiy eski funksiyalar (bo'lsa):
drop function if exists public.handle_new_user() cascade;
drop function if exists public.create_user_usage() cascade;
