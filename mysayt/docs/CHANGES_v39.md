# Slide Studio v39 — o'zgarishlar

## 1. Akkauntdan chiqib ketmaslik
- `index.html` (boshidagi skript): v38 qulfi saqlandi (slayd/media localStorage'ga yozilmaydi), lekin **faqat Supabase token** `ss-auth-v39` kaliti ostida saqlanadi.
- `js/03_auth_project.js`: `persistSession: true`, `storage: window.__ssAuthStorage`, `storageKey: 'ss-auth-v39'`.
- Tasodifiy `SIGNED_OUT` (tarmoq/token xatosi) endi sahifani qayta yuklamaydi va chiqarib yubormaydi — avval tiklashga urinadi (`ssRecoverSession`).
- `js/28_v39_fixes.js`: tab qaytganda / fokus / online / har 4 daqiqada tokenni yangilash.
- Supabase panelida tekshiring: **Authentication → Sessions**: "Time-box user sessions" va "Inactivity timeout" o'chiq (yoki katta) bo'lsin; **JWT expiry** 3600 s qoldirsa bo'ladi (refresh token ishlaydi).

## 2. Haqiqiy fayl sifatida saqlash
- Eksportdan (HTML / PPTX / PDF / JSON) oldin `ssEmbedAllMedia()` ishlaydi: `blob:`, `/api/proxy-image` va http rasm/GIF → `data:` (base64).
- Onlayn video (YouTube, Vimeo, http .mp4 havola) — havola bo'lib qoladi.
- Lokal video: 60 MB gacha `data:` sifatida slayd ichida (avval 4 MB edi, kattasi `blob:` bo'lib eksportda yo'qolardi). PPTX ichiga `addMedia({type:'video', data})` bilan **haqiqiy video** joylanadi.
- Eksportdan keyin faol slayd qayta yuklanadi, shuning uchun keyingi saqlashda ham `blob:` qaytib kelmaydi.

## 3. Media oynasi
- Slaydning bo'sh joyida 2 marta bosish (telefonda 2 marta tegish), yoki AI maydoniga `/fon`, `/rasm`, `/gif`, `/video`, `/media` yozish.
- Tashqariga bosilganda yopilmaydi — faqat ✕ yoki Esc.
- Qidirishda tepada yupqa progress, joylashda butun karta ustida aylanuvchi spinner (bloklaydi).
- Yangi rasm/GIF/video 260 ms ichida yumshoq paydo bo'ladi.

## 4. AI yozayotganda GIF/rasm
- GIF dekoder keshi (LRU) har 0.7 s da "pin" qilinadi — joriy taqdimot GIF'lari chiqarib yuborilmaydi.
- Xato GIF'lar qayta uriniladi, AI ishlayotganda kanvas muntazam qayta chiziladi, AI tugagach 4 marta qo'shimcha qayta chizish.
- `v39.css`: kanvas alohida GPU qatlamida (`translateZ(0)`, `contain`), yangi spinner/skelet animatsiyalari.

## Tekshirish ro'yxati
1. Kiring → F5 → akkaunt joyida qoladimi.
2. Kompyuterdan rasm + GIF + 10 MB video qo'ying → PPTX yuklab oling → boshqa kompyuterda PowerPoint'da oching.
3. Bo'sh joyni 2 marta bosing → oyna ochiladi; tashqariga bosing → yopilmaydi.
4. AI'dan uzun slayd yozdiring, GIF turib qoladimi.
