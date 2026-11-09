# v50 — slayd mazmuni yo'qolishi va reklama tuzatishlari

## Slayd (sayt, `js/08_canvas_slides.js`)
- **Sabab:** rasm/media bor varaq yuklanayotganda kanvas vaqtincha bo'sh bo'ladi. Shu payt `saveCurrentSlideState({force:true})`
  (asboblar tugmasi, o'lcham o'zgarishi va h.k.) bo'sh kanvasni varaqqa yozib yuborardi -> varaqda faqat fon qolardi.
  Keyin varaq almashtirilsa, bo'sh holat qayta saqlanardi.
- **Tuzatish:** yuklash tugamaguncha hech qanday saqlash (force ham) ishlamaydi (25 s himoya). Yuklashdan keyin 6 s ichida
  bo'sh kanvas varaqni o'chira olmaydi (qasddan o'chirish — `allowEmpty` — bundan mustasno). Yarim yuklangan kanvasdan
  chap paneldagi miniatyura endi olinmaydi.

## Reklama (bot, `backend/telegram_bot.py`)
- **«Joylash» bosilganda** reklama joylashuvi bot yoki ikkalasi bo'lsa, darrov botdagi hamma (Pro/VIP/admin bo'lmagan)
  foydalanuvchiga yuboriladi; tugagach hisobot keladi. («Hozir hammaga» tugmasi ham shu funksiyadan foydalanadi.)
- **Ko'rib chiqish (preview) xabari** endi ishonchli o'chadi: ro'yxat faylga yoziladi, har 15 s da tozalanadi, bot qayta
  ishga tushsa ham o'chadi (oldin oddiy `sleep` vazifasi yo'qolib qolardi).
- **Ikki tugma:**
  - `⏹ To'xtatish` — reklama saytdan ham, botdan ham (yangi yuborishdan) to'xtaydi; chatlarga yuborilgan xabarlar qoladi.
    Tugagan reklamani `▶️ Yoqish` qilsa yana 24 soat beriladi.
  - `🗑 Botdan ham o'chirish` — reklama butunlay o'chadi va foydalanuvchilar chatidan ham olib tashlanadi.
- **Muddat tugaganda** reklama avtomatik «tugadi» holatiga o'tadi (saytdan chiqadi), yozuv va statistika O'CHMAYDI.
  Chatdagi xabarlar qoladi. Agar tugaganda chatdan ham o'chirish kerak bo'lsa — admin sozlamada `ad_purge_on_expire = true`.
- Tozalovchi (sweeper) endi bot ishga tushganda o'zi boshlanadi.
