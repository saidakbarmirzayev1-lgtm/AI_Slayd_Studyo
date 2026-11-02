# v43 — Telegram bot (webhook) + barqarorlik

## Ulash (3 qadam)
1. Render -> Environment: `TELEGRAM_BOT_TOKEN` = BotFather tokeni; `PUBLIC_BASE_URL` = https://ai-slaydstudyo.onrender.com
   (lokal `.env` ga ham: `TELEGRAM_BOT_TOKEN="1234567890:AAA..."`).
2. Deploy qiling. Server ishga tushganda webhook, buyruqlar va menu tugmasi O'ZI o'rnatiladi (qo'lda setWebhook shart emas).
3. Botga /start yozing.

## Yangi
- backend/telegram_bot.py — POST /telegram-webhook (darhol 200, fonda ishlov), /start /credits /site /help,
  matn = mavzu -> Mini App tugmasi (?topic=...), 💳 Kreditlarim tugmasi.
- POST /api/telegram/auth — Mini App ichida Telegram orqali avtomatik kirish (initData imzosi tekshiriladi).
- js/33_v43_telegram.js — avto-kirish, to'liq ekran, botdan kelgan mavzuni AI'ga avtomatik yuborish.
- Sozlamalardan balans ("AI varaqlar") bo'limi olib tashlandi (balans yuqoridagi ⚡ tugmasida qoladi).

## Barqarorlik / RAM / log
- uvicorn.run("main:app") butun main.py ni 2-marta yuklardi (RAM 2x, admin panel boshqa nusxani o'zgartirardi) -> app obyekti beriladi.
- access_log o'chirildi, log_level=warning (LOG_LEVEL bilan o'zgartiriladi).
- Har 10 daqiqada: eskirgan sessiyalar, rate-limit, host-semaforlar, buyurtma ID lari tozalanadi + gc.
- WebSocket ping 25s / timeout 60s (mobil fon rejimida uzilishlar kamayadi). MALLOC_ARENA_MAX=2.
- v39.css / v40.css serverda 404 edi (PUBLIC_STATIC_FILES da yo'q) — qo'shildi.
- X-Frame-Options -> CSP frame-ancestors (Telegram Web/Desktop iframe uchun).
