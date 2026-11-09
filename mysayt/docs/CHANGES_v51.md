# v51 — bot oqimi qayta qurildi, Google o'chsa bot to'xtaydi, reklama o'chirish va sayt reklamasi

## Bot oqimi (`backend/telegram_bot.py`)
- **/start** admin uchun ham, mijoz uchun ham BIR XIL (salomlashish + pastki menyu). Admin paneli o'zi ochilmaydi —
  faqat admin **`admin`** deb yozsa ochiladi (boshqalarga hech narsa oshkor bo'lmaydi).
- **Tugma bosilmasdan** yozilgan matn endi AI'ga ketmaydi va eski slaydni ham o'zgartirmaydi:
  bot «Avval 🎨 Yangi slayd yoki 📂 Slaydlarim ni tanlang» deydi.
- **🎨 Yangi slayd** rejimi: AI o'zi hal qiladi — mavzu yozilsa slayd yasaydi; oddiy savol/salomlashuv bo'lsa slayd
  yasamasdan javob beradi (varaq sarflanmaydi, rejim saqlanadi). «slayd/taqdimot/N ta» so'zi bo'lsa — darrov yasaydi.
- **Slayd tayyor bo'lganda**: fayllar avtomatik tashlanmaydi. Tayyor matn (sarlavha + slaydlar ro'yxati) va tagida
  **📊 PPTX · 📕 PDF · 🌐 HTML** tugmalari + bitta **✏️ Tahrirlash** (+ Yangi slayd / Slaydlarim). Format tugmasi bosilsa — fayl o'zi yuboriladi.
- **✏️ Tahrirlash oynasi**: slayd matni, misollar, **🚀 Muharrirda ochish / 🌐 Brauzerda** (aynan shu slaydning o'zi ochiladi),
  🎨 Rang, ✅ Tayyor. Faqat shu oynada yozilgan matn tahrir sifatida AI'ga boradi.
- **📂 Slaydlarim** → saqlangan slaydni bosilsa xuddi shu karta (matn + 3 tugma + Tahrirlash) chiqadi.
- Yuklama himoyasi: AI navbatida 30 tadan ko'p so'rov bo'lsa yangisi «Hozir so'rovlar ko'p» deb qaytariladi (server qotmaydi).

## Google akkaunt Supabase'dan o'chirilsa
- Sabab: bot akkauntni xotirada (kesh) abadiy eslab qolardi. Endi har 45 soniyada tekshiriladi: Google foydalanuvchi
  Supabase Auth'da yo'q bo'lsa ulanish (`tg_links`) o'chadi va bot yana «Google ulang» deydi (admin bundan mustasno).
  Baza vaqtincha javob bermasa — hech kim bloklanmaydi.

## Reklama
- **Botda to'liq o'chirilganda xabar chatda qolib ketishi**: yuborilgan xabarlar ro'yxati serverning `/tmp` fayliga yozilardi
  (Render'da har deploy/restartda yo'qoladi). Endi Supabase'dagi `ad_sent` jadvalida saqlanadi va restartdan keyin ham tiklanadi.
  **Bir marta `SUPABASE_AD_SENT.sql` ni ishga tushiring** (jadval bo'lmasa bot eskicha, faqat fayl bilan ishlaydi).
- Baza vaqtincha javob bermay qolsa, jonli reklama xabarlari noto'g'ri o'chirib yuborilmaydi (tekshiruv «noma'lum» bo'lsa — tegilmaydi).
- 1000 ta foydalanuvchiga yuborishda bot qotmasligi uchun: ro'yxat har xabarda butun faylga yozilmaydi (15 s da bir marta, alohida oqimda);
  reklama rasmi Telegram'ga BIR marta yuklanadi, qolganlarga `file_id` bilan yuboriladi.
- «📋 Kimlarga yetdi/yetmadi» hisoboti sahifalanadi (30 tadan, ‹ Oldingi / Keyingi ›).
- **Sayt/muharrir**: sahifa yangilanganda reklama kartasi chap panel qayta chizilganda o'chib qolardi — endi panel kuzatiladi va
  panel kech paydo bo'lsa qayta urinadi. Bir xil reklama 60 soniyalik yangilanishda ko'rsatishga qayta sanalmaydi.

## Tekshiruv
`python tests/test_v51_flow.py` — soxta Telegram/AI bilan butun oqim (start, tugmasiz matn, yangi slayd + savol, tahrirlash oynasi,
fayl tugmasi, Google o'chishi, reklama bazadan tiklanishi va o'chirilishi).
