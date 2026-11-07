# Slide Studio AI (v37)

AI yordamida professional slayd / taqdimot yaratish (Fabric.js + AI + Supabase). Ko'p tilli: AI foydalanuvchi tilida javob beradi.

## Lokal ishga tushirish
```bash
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env     # kalitlarni to'ldiring
python main.py           # http://localhost:8080
```

## Internetga chiqarish (tavsiya: Render / Railway / Fly.io / VPS)
1. Kodni **private** GitHub repo ga yuklang (`.env` yuklanmaydi — `.gitignore` da).
2. Render: *New → Blueprint* → repo ni tanlang (`render.yaml` tayyor) yoki *Web Service → Docker*.
3. Environment bo'limiga `.env.example` dagi MAJBURIY qiymatlarni kiriting.
   `PUBLIC_BASE_URL` = sizning sayt manzilingiz (https://...).
4. Supabase: `SUPABASE_SETUP.sql` ni SQL Editor da bir marta ishga tushiring (hamma jadvallar bitta faylda).
   Authentication → URL Configuration: *Site URL* va *Redirect URLs* ga sayt manzilini qo'shing.
   Google Cloud Console → OAuth client → *Authorized redirect URIs* ga Supabase callback manzilini qo'shing.
5. Lemon Squeezy webhook: `https://SAYT/api/payment/lemon-webhook`.
6. Tekshiruv: `https://SAYT/healthz` → `{"ok":true,"ai":true,"auth":true}`.

Docker: `docker build -t slide-studio . && docker run -p 8080:8080 --env-file .env slide-studio`

## Xavfsizlik ro'yxati
- `SUPABASE_SECRET_KEY`, `AI_API_KEY` faqat serverda (env). Hech qachon gitga yozmang.
- `SLIDE_STUDIO_HMAC_SECRET` ni uzun tasodifiy qiymatga qo'ying. `SLIDE_STUDIO_DEV_MODE` productionda bo'sh bo'lsin.
- HTTPS majburiy (Render/Cloudflare avtomatik beradi).

## Muammo?
Brauzerda Ctrl+F5. Server logida `[AI]`, `[GIF]`, `[IMG-SEARCH]` yozuvlarini qarang. GIF yaxshiroq bo'lsin desangiz `KLIPY_API_KEY` yoki `GIPHY_API_KEY` qo'shing.

### v38 o'zgarishlari
- Rasm/GIF/video faqat foydalanuvchi qurilmasi RAM'ida (Blob URL); serverda disk keshi yo'q (`.img_cache` olib tashlandi), proksi faqat CORS bermaydigan saytlar uchun zaxira.
- localStorage/sessionStorage ishlatilmaydi; sessiya faqat RAM'da (Google popup + BroadcastChannel). Sahifa yangilansa qayta kirish kerak, kirgach oldingi loyihalar ochish taklif qilinadi.
- Yuklanish skeleti foiz bilan, miltillamaydigan slayd almashish, real-time sidebar.
- Taqdimotdan oldin barcha media RAM'ga yuklanadi.
- Schyotni nusxalash/joylash: eng oxirgi nusxa (ichki yoki tashqi); tashqi drag-drop (fayl, matn, video).
- **Yagona kredit hisobi** (faqat serverda, Supabase `user_usage`): balans birlikda (1 Tez-varaq = 20, 1 Chuqur-varaq = 60).
  Tez AI: bepul 15 varaq/kun, $1 = 150 varaq; slayd = 1 varaq, 4 savol-javob = 1, 5 qidiruv = 1.
  Chuqur AI: bepul 5 varaq/kun, $1 = 50 varaq; slayd = 1, 4 savol-javob = 1, 4 qidiruv = 1.
  Rejim almashganda balans avtomatik qayta hisoblanadi.
- Supabase'da slaydlar/tarix SAQLANMAYDI — faqat akkaunt (Auth) va balans. **Deploydan oldin `SUPABASE_SETUP.sql` ni Supabase SQL Editor da bir marta ishga tushiring (noldan to'liq sozlaydi).**
- Matn doim eng tepa qatlamda.
- Deploy: Render.com (`render.yaml`), env o'zgaruvchilar `.env.example` da. `.env` ni HECH QACHON GitHub'ga yuklamang.


## v40
Eksport yangilandi (PPTX havola/tugma/MP4/YouTube, mustaqil HTML namoyish, PDF havolalari). Batafsil: `docs/CHANGES_v40.md`.

## v41
Namoyish jonli ko'rsatgichga o'tkazildi, oldindan yuklash + kesh, IndexedDB'da doimiy saqlash, PPTX video/GIF, bitta PDF ogohlantirish, balans oynasi z-index. Batafsil: `docs/CHANGES_v41.md`.

## v42
PPTX galereya videosi (haqiqiy MP4), Namoyish tugmalari olib tashlandi, tezkor javob, balans oynasi. Batafsil: `docs/CHANGES_v42.md`.

## v44
Mobil siljish tuzatildi, balans bloki sig'adi, Telegram bot to'liq qayta yozildi (AI slayd + PPTX/PDF/HTML). Batafsil: `docs/CHANGES_v44.md`.

## v46
Avto-saqlash o'chirildi (sahifa doim toza), Ctrl+Z tuzatildi, «Rasmni tozalash» va «Bot haqida», botda fayl → «Redaktorda ochish», «Sozlamalar». Batafsil: `docs/CHANGES_v46.md`.
