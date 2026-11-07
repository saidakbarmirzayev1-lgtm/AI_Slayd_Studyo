# v47 — Pro, reklama, yangi admin panel, bot va sayt tuzatishlari

## 1) Ishga tushirish (3 qadam, tartib bilan)
1. **Supabase → SQL Editor** → `SUPABASE_ADMIN.sql` ni bir marta ishga tushiring (Pro/cheksiz ustunlari, reklama, sozlamalar, jurnal jadvallari).
2. **Render → Environment**ga yozing:
   - `ADMIN_TG_IDS` — sizning Telegram ID'ingiz (botga `/id` deb yozsangiz chiqadi)
   - `ADMIN_EMAILS` — admin Google emailingiz
   - Pro to'lovi uchun: Lemon Squeezy'da **Pro mahsulot** (bir martalik, $5) yarating → `LEMON_SQUEEZY_PRO_VARIANT_ID`, kerak bo'lsa `PRO_PRICE_USD`, `PRO_DAYS`.
3. Botda Google akkauntingizni ulang (⚙️ Sozlamalar → ulash). So'ng botga **admin** deb yozing → panel tugmasi chiqadi.

> Supabase → Authentication → Providers → Email da **"Confirm email" yoqilgan** bo'lib qolsin (admin emailini boshqa birov egallay olmasligi uchun).

## 2) Admin panel (noldan yozilgan)
* Ochiq manzili yo'q. Faqat: botda `admin` (Telegram ID + ulangan Google email **ikkalasi** mos bo'lsa) yoki saytda ⚙️ Sozlamalar ichidagi yashirin «🛡 Admin panel» (faqat admin akkauntga ko'rinadi).
* Boshqalar `admin` desa — oddiy matn sifatida javob oladi; `/_a/...` har doim 404.
* Imkoniyatlar: statistika; foydalanuvchi qidirish (email / TG ID / user_id); **Pro / VIP / bepul** berish (muddat bilan yoki muddatsiz); **cheksiz** yoqish; varaq qo'shish/ayirish/aniq o'rnatish; shaxsiy kunlik limit; bloklash; izoh; reklama CRUD (rasm yuklash, video havola, havola, joylashuv, jadval, ustuvorlik, statistika); limit/Pro/reklama/texnik-ishlar/e'lon sozlamalari (darhol qo'llanadi); ommaviy xabar (bot); tizim holati va baza tekshiruvi; AI kalitini almashtirish; serverni to'xtatish; balans/to'lov/admin jurnallari.
* Admin akkauntlar (Google email va admin Telegram akkaunti) avtomatik **VIP**: cheksiz va reklamasiz.

## 3) Pro
* Pro = muddatli reja (`PRO_DAYS`, standart 30 kun): **reklamasiz** + kuniga ko'proq bepul varaq (`PRO_DAILY_PAGES`). Muddati tugasa avtomatik bepulga qaytadi.
* Botda: `/pro`, «👑 Pro» tugmasi, balansda. Saytda: ⚙️ Sozlamalar → Pro kartasi. To'lov Telegram ichida tashqi brauzerda ochiladi.
* To'lov botda ishlamasa: oddiy foydalanuvchi mayin xabar ko'radi, **admin esa aniq sababni** (qaysi env yetishmaydi) ko'radi. Vaqtincha admin paneldan qo'lda Pro berish mumkin.
* Webhook: Pro buyurtma muddatni uzaytiradi, qaytarilsa (refund) ayiradi; paketlar avvalgidek; ikki marta hisoblanmaydi.

## 4) Reklama
* Saytda: chap panelda, slaydlar tagida (rasm/video + matn + havola). Botda: taqdimot yuborilgach (oraliq — sozlama, standart 15 daqiqa).
* **Pro / VIP / admin / cheksiz foydalanuvchilarga ko'rsatilmaydi** — qaror serverda.
* Ko'rsatilish/bosilish hisoblanadi (CTR). Havola serverdan o'tib hisoblanadi, faqat http/https.

## 5) Balans (bitta akkaunt = bitta balans)
Hisob avvalgidek `user_usage` jadvalida; Telegram + Google ulanganda botda ham saytda ham aynan shu qator ishlatiladi. Kredit yechish serverda qulf bilan; cheksiz/VIP uchun hech narsa yechilmaydi.

## 6) Bot interfeysi
Yangi pastki menyu (2 ustun, «🚀 Muharrir» Mini App tugmasi), karta ko'rinishidagi balans (progress bar), reja nishoni (Bepul / Pro / VIP), Pro kartasi, tartibli sozlamalar.

## 7) Sayt tuzatishlari
* **Sozlamalar tugmasi**: tepada doim ko'rinadigan ⚙️ + ishonchli oyna; sidebar yopiq bo'lsa ham ishlaydi; ikki marta ochilmaydi. Eski asboblar «🛠 Asboblar va tozalash» orqali.
* **Fon rasmi / rasm yuklash tugmalari**: Telegram/iOS WebView'da DOM'ga ulanmagan `<input type=file>` tanlangan faylni bildirmasdi — endi ulanadi.
* Faol slaydga qayta bosilganda keraksiz qayta chizish yo'q.
* ∞ (cheksiz/VIP), PRO/VIP nishoni; cheksiz foydalanuvchini limit oynasi to'smaydi.

## 8) Sinov
`python -m pytest tests -q` (22 ta backend sinov) va `tests/frontend_v47.test.js` (jsdom). Haqiqiy brauzer/Telegram'da qo'lda tekshirish tavsiya etiladi.
