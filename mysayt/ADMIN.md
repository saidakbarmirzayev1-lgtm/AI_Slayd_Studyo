# Admin panel

## .env (Render Environment)
```
ADMIN_TELEGRAM_IDS=SIZNING_TELEGRAM_ID
ADMIN_EMAILS=siz@gmail.com
AD_ENABLED=1
AD_TITLE=Slide Studio AI
AD_TEXT=Professional slaydlar — Slide Studio AI
AD_URL=https://t.me/your_bot
AD_BUTTON=Botga o'tish
```

Telegram ID ni bilish: @userinfobot ga yozing.

## Bot buyruqlari
- `/admin` — panel
- `/admin pro 123456789` — PRO berish
- `/admin unlimited 123456789` — cheksiz
- `/admin refill 123456789` — bugungi limit
- `/admin broadcast Matn...` — hammaga reklama
- `/admin stats` — statistika

PRO / admin ga reklama varog'i **qo'yilmaydi**.
Boshqalarga PPTX/PDF oxiriga avtomatik reklama varog'i qo'shiladi.

## Supabase
`SUPABASE_ADMIN.sql` ni SQL Editor da ishga tushiring (ixtiyoriy).
