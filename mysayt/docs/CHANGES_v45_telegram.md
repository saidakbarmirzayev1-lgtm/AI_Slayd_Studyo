# v45 — Telegram bot: stateless, bitta baza, tahrirlash, yangi interfeys

## O'rnatish (3 qadam)
1. Supabase → SQL Editor → `SUPABASE_TELEGRAM.sql` ni ishga tushiring (3 ta kichik jadval: `tg_links`, `tg_link_codes`, `tg_decks`).
2. Kodni GitHub'ga yuklang (Render o'zi qayta deploy qiladi).
3. Render env: `TELEGRAM_BOT_TOKEN`, `PUBLIC_BASE_URL`, `SUPABASE_SECRET_KEY`, Lemon Squeezy kalitlari (mavjud). Yangi env kerak emas.
Jadvallar yaratilmasa ham bot ishlaydi — faqat slaydlar tarixi restartda yo'qoladi va «Telegram ulash» ishlamaydi.

## 1. Serverda fayl saqlanmaydi
- PPTX/PDF/HTML faqat RAM'da yasaladi (`decks.export_all` -> bayt), Telegram'ga yuboriladi, ro'yxatdan `pop` qilinib darhol bo'shatiladi, so'ng `gc.collect()`.
- Rasmlar ham yuborishdan keyin RAM'dan tozalanadi (yuborilmay qolsa 10 daqiqada). Diskka yozish YO'Q (test bilan tekshirilgan).
- Bazada faqat: foydalanuvchi, balans, qisqa slayd JSON (matn, har kishiga oxirgi 5 ta).
- Bot qayta ishga tushsa ham (Render uxlab uyg'onsa) oxirgi slayd bazadan tiklanadi — tahrirlash/qayta yuklash ishlayveradi.

## 2. Yagona baza va balans
- Balans `user_usage` jadvalida; bot har safar bazadan yangi o'qiydi (kesh yo'q).
- Telegram akkaunt: `tg<ID>@t.me`. Google bilan kirgan sayt akkauntini ulash: saytda balans panelidagi **«✈️ Telegram»** -> kod -> botda `/link KOD` (yoki «Telegramda ochish» tugmasi). Ulangach bot, Mini App va sayt BITTA akkaunt balansini ishlatadi. Oldin botda sotib olingan pullik varaqlar sayt akkauntiga ko'chadi (bepullari emas).
- Botda slayd yaratilsa — saytda balans oynaga qaytganda / har 30 soniyada yangilanadi. Saytda (yoki botda) to'lov bo'lsa — botga darhol «✅ To'lov qabul qilindi +N varaq» xabari keladi.
- Botdagi «💎 Varaq sotib olish» to'g'ridan-to'g'ri Lemon Squeezy checkout yaratadi (sayt bilan bir xil kod: `_build_checkout`).

## 3. Matnli tahrirlash (butun taqdimotni qayta yozmaydi)
- AI endi butun deck o'rniga **amallar** qaytaradi: `replace / insert / delete / move / meta`. Tegilmagan slaydlar aynan o'zgarishsiz qoladi.
- «3-slaydni…» deb yozilsa AI'ga faqat shu slayd(lar) to'liq JSON'i + barcha slaydlar sarlavhalari yuboriladi (token tejaladi, tezroq).
- Titul slayd o'chirilmaydi, yakunlovchi slayd doim oxirida qoladi. Narx: o'zgargan/qo'shilgan slaydlar soni (matn-rang o'zgarishi faqat chat narxi).
- Tahrirdan keyin yangilangan PPTX + PDF + HTML qaytariladi, baza yangilanadi.

## 4. Interfeys
- Doimiy pastki menyu: 🎨 Yangi slayd yaratish · 📂 Slaydlarim / Tozalash · 💳 Balans / To'ldirish · 🌐 Saytga o'tish.
- /start: ismi bilan salom + bepul/pullik balans + yangilanish vaqti.
- Mavzu yozilishi bilan: bosqichli holat (⏳ tahlil -> 🧠 matn -> 🖼 rasm -> 📦 fayllar) va 3 ta fayl birdan. Slayd soni so'ralmaydi (standart 8; «10 ta slayd» desa o'zi oladi).
- 📂 Slaydlarim: oxirgi 5 ta ro'yxat (ochish) va «🗑 Hammasini tozalash» (tasdiq bilan; balans va akkaunt saqlanadi).
- Buyruqlar: /start /new /my /clear /credits /buy /link /unlink /mode /site /help.

## Fayllar
`backend/telegram_bot.py` (asosiy), `main.py` (to'lov: `_build_checkout`, webhook -> `notify_purchase`), `js/35_v45_tglink.js` (+ `index.html`), `SUPABASE_TELEGRAM.sql`, `.gitignore`.
