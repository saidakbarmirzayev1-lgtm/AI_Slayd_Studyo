# v46

## Sayt
- **Avto-saqlash o'chirildi** (`js/30_v40_present_persist.js`): slaydlar IndexedDB/localStorage'ga yozilmaydi, eski saqlangan loyiha o'chiriladi.
  Sahifa ochilsa/yangilansa har doim toza, yangi slayd (telefon va kompyuterda bir xil). Faqat Google login tokeni saqlanadi.
- **Ctrl+Z tuzatildi** (`js/38_v46_fixes.js`): tarixning birinchi qadami endi doim toza boshlang'ich holat. Avval (loyiha tiklangan/import qilingan bo'lsa)
  birinchi yozuv birinchi rasm qo'yilgandan keyingi holat bo'lib, Ctrl+Z shu rasmda to'xtardi.
- **«Rasmni tozalash»** tugmasi (sidebar, «Slayd qo'shish» tagida): hamma narsani birinchi holatga qaytaradi; Ctrl+Z bilan qaytariladi.
- **«Bot haqida»** tugmasi (sidebar) — loyiha, ishlash tartibi, akkaunt/balans, narx, maxfiylik.
- `?tgfile=TOKEN` — botdan kelgan rasm/GIF/video/PPTX/PDF/HTML muharrirda ochiladi.

## Telegram bot (`backend/telegram_bot.py`)
- Istalgan **rasm / fayl / video / GIF** yuborilsa — «✏️ Redaktorda ochish» (Mini App) va «🌐 Brauzerda ochish» tugmalari chiqadi.
  Fayl faqat RAM'da 15 daqiqa turadi (diskka/bazaga yozilmaydi), havola imzolangan va faqat shu chatga tegishli (`GET /api/telegram/file`).
  `.pptx` bo'lsa qo'shimcha «🤖 AI bilan matnini tahrirlash».
- **⚙️ Sozlamalar** (/settings): Google ulanganmi, «Google'ni uzish» / «Google akkauntni ulash», Tez/Chuqur AI rejimi.
- **ℹ️ Bot haqida** (/about).
- /start: Google ulanmagan bo'lsa «🔗 Google akkauntni ulash» taklifi chiqadi.
- Yagona balans va 1 Telegram = 1 Google (`tg_links`: tg_id PK, user_id UNIQUE) — v45'dan beri bor, o'zgarmadi.

Yangi env / SQL kerak emas.
